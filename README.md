## About

This utility can listen webhooks from Docker Hub and (re)deploy services and stacks on webhook call.


## Configuration

See `config-sample.json` to view sample configuration.

See Dockerfile label `run` to view example docker run command.


## Volumes

This image require following volumes to be established to be able to operate:

- `config.json`: configutation file
- `docker.sock`: docker local socket, for `docker stack` and `docker service` commands works
- docker stacks directory (if you use stack deploys)
