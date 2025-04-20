
# Core Saida Infrastructure!

This project is set up like Python project using poetry package manager.

The `cdk.json` file tells the CDK Toolkit how to execute your app.


## Setup
```
# create virtualenv
$ poetry env activate

# install dependencies
(.venv)$ poetry install

```

## Develop the code for the stack
```
# use cdk to deploy infrastructure
# ensure your AWS credentials are set, then
cdk synth
cdk deploy

```


Cookiecutter from
https://github.com/vino9org/cookiecutter-python-cdk-stack

Good References on:
https://github.com/ran-isenberg/cookiecutter-serverless-python
