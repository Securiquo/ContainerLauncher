import uuid
from azure.identity import AzureCliCredential
from azure.mgmt.containerinstance.models import *
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from flask import request, app, Flask, jsonify
from flask_cors import CORS, cross_origin
import os
import json

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


def create_aci_client(credential, subcription_id):
    return ContainerInstanceManagementClient(credential, subcription_id)


def get_rg(resource_client, rg_name):
    group_list = resource_client.resource_groups.list()
    rg = ""
    for i in group_list:
        if i.name == rg_name:
            rg = i
    return rg


def get_acr_credentials():
    password=os.getenv("ACRPASSWORD")
    return [ImageRegistryCredential(server='acrsecuritumdev.azurecr.io', username='acrsecuritumdev',
                                    password=password)]


def initial():
    credential = AzureCliCredential()
    subscription_id = "c195877f-eee3-4368-a9b3-525a5be23d0b"
    resource_client = ResourceManagementClient(credential, subscription_id)

    return credential, subscription_id, resource_client


@app.route("/api/open", methods=["POST"])
def open_container():
    container_image_name = request.args.get("container_image_name")
    flag = request.args.get("flag")
    unique_id = uuid.uuid4()
    app_name = "app" + str(unique_id)
    credential, subscription_id, resource_client = initial()

    rg = get_rg(resource_client, "acr-rg")
    aciclient = create_aci_client(credential, subscription_id)
    acr_credentials = get_acr_credentials()

    container_type = "Public"
    container_resource_requests = ResourceRequests(memory_in_gb=2, cpu=1.0)
    command_flag = EnvironmentVariable(name='flag', value=flag)
    container_resource_requirements = ResourceRequirements(
        requests=container_resource_requests)

    f = open('./db_image_information.json')
    images = json.load(f)
    containers = []
    ports = []
    container_app = {}

    for image in images:
        if image["appName"] == container_image_name:
            container_app = image

    for j in range(0, len(container_app["imageName"])):
        containers.append(Container(name=str("{0}{1}".format(container_image_name, j)),
                                    image="acrsecuritumdev.azurecr.io/{0}:v1".format(container_app["imageName"][j]),
                                    resources=container_resource_requirements,
                                    environment_variables=[command_flag],
                                    ports=[ContainerPort(port=container_app["ports"][j])]))

        ports.append(Port(protocol=ContainerGroupNetworkProtocol.tcp, port=container_app["ports"][j]))

    group_ip_address = IpAddress(ports=ports,
                                 dns_name_label=app_name,
                                 type=container_type)

    group = ContainerGroup(location=rg.location,
                           containers=containers,
                           os_type=OperatingSystemTypes.linux,
                           restart_policy=ContainerGroupRestartPolicy.never,
                           image_registry_credentials=acr_credentials,
                           ip_address=group_ip_address)

    aciclient.container_groups.begin_create_or_update(rg.name,
                                                      app_name,
                                                      group)

    return jsonify(success=True, app_name=app_name)


@app.route("/api/close", methods=["POST"])
def close_container():
    resource_group_name = "acr-rg"
    container_group_name = request.args.get("container_group_name")

    credential, subscription_id, resource_client = initial()
    aciclient = create_aci_client(credential, subscription_id)
    aciclient.container_groups.begin_delete(resource_group_name,
                                            container_group_name)
    return jsonify(success=True)

