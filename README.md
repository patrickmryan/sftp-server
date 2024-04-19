# sftp server with EFS storage

This stack deploys a private sftp server using AWS Transfer. The underyling storage is an AWS EFS
file system. User accounts are set up using a key pair.

## cdk.json parameters

| Parameter | Purpose |
| ------------- | ------------ |
| VpcId | ID of the VPC where the sftp server will be attached. |
| SubnetIds | List of subnets to be used for allocating ENIs. |
| CidrRanges | List of CIDR ranges that will be allowed in. |
| PermissionsBoundaryPolicyName | (Optional) Permissions boundary added to created roles. |
| IamRolePath | (Optional) Path prepended on IAM roles and policies. |
| Users | (Optional) A key-value set indicating the username, key file, numeric user id and group id. Users may be added later. |
