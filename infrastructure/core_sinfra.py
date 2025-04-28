import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
from aws_cdk import Stack
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as _s3
from bhub_cdk.common import BusinessUnit
from bhub_cdk.vpc import PrivateSubnets, Vpc
from constructs import Construct

from infrastructure.database import DatabaseInstance


class CoreSaidaInfrastructure(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = Vpc.shared(self)
        vpc_subnets = PrivateSubnets.select_for(self, BusinessUnit.CAAS)

        repository_name = "core-saida/orchestrator"
        repository_construct_id = f"{construct_id}ECRImageRepository"
        try:
            ecr_repository = ecr.Repository.from_repository_name(
                self, repository_construct_id, repository_name=repository_name
            )
        except Exception:
            ecr_repository = ecr.Repository(
                self, repository_construct_id, repository_name=repository_name
            )

        cdk.aws_ssm.StringParameter(
            self,
            f"{construct_id}EcrRepoArnParameter",
            parameter_name="/core-saida/ecr-repository-uri",
            string_value=ecr_repository.repository_uri,
        )

        self.orchestrator_application = OrchestratorApplication(
            self,
            "OrchestratorApp",
            vpc=vpc,
            vpc_subnets=vpc_subnets,
            ecr_repository=ecr_repository,
        )


class OrchestratorApplication(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        vpc_subnets: ec2.SubnetSelection,
        ecr_repository: ecr.IRepository,
    ) -> None:
        super().__init__(scope, construct_id)

        self.ecr_repository = ecr_repository
        self.construct_id = construct_id
        self.account_id = cdk.Stack.of(self).account

        self.dp_bucket = _s3.Bucket(
            self,
            "CoreSaidaBucket",
            bucket_name="core-saida",
            encryption=_s3.BucketEncryption.S3_MANAGED,
            versioned=False,
            block_public_access=_s3.BlockPublicAccess.BLOCK_ACLS,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        self.database_instance = DatabaseInstance(
            self,
            f"{self.construct_id}DatabaseInstance",
            database_name="core_saida_orchestrator",
            vpc=vpc,
            vpc_subnets=vpc_subnets,
        )

        self.cluster = ecs.Cluster(
            self,
            "OrchestratorCluster",
            vpc=vpc,
            container_insights=True,
            enable_fargate_capacity_providers=True,
        )

        taskExecutionRole = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        taskExecutionRole.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )

        taskExecutionRole.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                resources=["*"],
            )
        )

        taskExecutionRole.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[self.database_instance.secret.secret_arn],
            )
        )

        taskExecutionRole.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:*"],
                resources=[self.dp_bucket.bucket_arn, f"{self.dp_bucket.bucket_arn}/*"],
            )
        )

        # Add specific secret access permission
        taskExecutionRole.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[f"arn:aws:secretsmanager:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:secret:OrchestratorAppOrchestrator-*"],
            )
        )

        task_definition = ecs.FargateTaskDefinition(
            self,
            "OrchestratorTaskDef",
            memory_limit_mib=512,
            cpu=256,
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.X86_64,
            ),
            task_role=taskExecutionRole,
        )

        container = task_definition.add_container(
            "OrchestratorContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                repository=self.ecr_repository, tag="latest"
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="OrchestratorApp",
                log_retention=logs.RetentionDays.ONE_WEEK,
            ),
        )

        container.add_port_mappings(
            ecs.PortMapping(
                container_port=8000,
                host_port=8000,
            ),
        )

        self.orchestrator_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "OrchestratorService",
            cluster=self.cluster,
            task_definition=task_definition,
            desired_count=1,
            service_name="OrchestratorService",
            assign_public_ip=False,
            public_load_balancer=True,
            listener_port=80,
            load_balancer_name="OrchestratorLoadBalancer",
        )

        self.orchestrator_service.task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[self.database_instance.secret.secret_arn],
            )
        )

        scalable_target = self.orchestrator_service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2,
        )

        scalable_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
        )
        scalable_target.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
        )

        self.orchestrator_service.load_balancer.apply_removal_policy(
            cdk.RemovalPolicy.DESTROY
        )

        self.orchestrator_service.target_group.configure_health_check(
            path="/health",
            interval=cdk.Duration.seconds(30),
            timeout=cdk.Duration.seconds(5),
            enabled=True,
        )

        self.secrets = {
            "DATABASE_SECRET": self.database_instance.secret,
        }

        self.environment = {
            "AWS_DP_BUCKET_NAME": self.dp_bucket.bucket_name,
            "PGSQL_HOST": self.database_instance.host,
        }
