from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_rds as rds
from constructs import Construct

PGSQL_DEFAULT_PORT = 5432
PGSQL_DEFAULT_USERNAME = "postgres"


class DatabaseInstance(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        database_name: str,
        vpc: ec2.IVpc,
        vpc_subnets: ec2.SubnetSelection,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._instance = rds.DatabaseInstance(
            self,
            construct_id,
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16_6),
            database_name=database_name,
            vpc=vpc,
            vpc_subnets=vpc_subnets,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            backup_retention=Duration.days(15),
            deletion_protection=True,
            copy_tags_to_snapshot=True,
            removal_policy=RemovalPolicy.RETAIN,
            enable_performance_insights=True,
        )

        self._proxy = rds.DatabaseProxy(
            self,
            f"{construct_id}RdsProxy",
            proxy_target=rds.ProxyTarget.from_instance(self._instance),
            secrets=[self._instance.secret],
            vpc=vpc,
            vpc_subnets=vpc_subnets,
        )

        self.secret = self._instance.secret
        self.host = self._proxy.endpoint

        # TODO should only allow any_ipv4 in dev environment, production should be limited to the VPC CIDR
        self._instance.connections.allow_from(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(PGSQL_DEFAULT_PORT),
            description="Allow PostgreSQL connections to RDS instance",
        )

        self._proxy.connections.allow_from(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(PGSQL_DEFAULT_PORT),
            description="Allow PostgreSQL connections to RDS Proxy",
        )

    def allow_function_to_connect(self, function: lambda_.Function):
        """Allow the given Lambda function to connect to the database.

        Parameters
        ----------
        function : lambda_.Function
            The Lambda function to be allowed to connect to the database

        """
        self._proxy.grant_connect(function.role, PGSQL_DEFAULT_USERNAME)
        function.connections.allow_to(self._proxy, ec2.Port.tcp(PGSQL_DEFAULT_PORT))
