from fastapi import FastAPI, HTTPException, Body
import requests
import paramiko
from models.registration import NodeParams, Kubeparam
from models.cluster import ClusterRequest
import os
app = FastAPI()



@app.get("/")
async def hello():
    return {"massage" :  "Welcome in rancher registration API !"}   



# Cluster Creating Part

@app.post("/create-cluster/")
def create_cluster(request: ClusterRequest):
    headers = {
        "Authorization": f"Bearer {request.access_token}",
        "Content-Type": "application/json",
    }

    create_cluster_payload = {
        "type": "cluster",
        "name": request.cluster_name,
        "rancherKubernetesEngineConfig": {
            "kubernetesVersion": request.kubernetes_version
        }
    }

    try:
        response = requests.post(
            f"{request.rancher_url}/clusters", headers=headers, json=create_cluster_payload, verify=False
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error creating cluster: {str(e)}")

    if response.status_code == 201:
        cluster_id = response.json().get('id')
        return {"message": "Cluster created successfully", "cluster_id": cluster_id}
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Error creating cluster: {response.text}")



# registration part



def get_kubeconfig(param: Kubeparam) -> str:
    try:
        url = f"{param.rancher_url}/v3/clusters/{param.cluster_id}/kubeconfig"
        headers = {
            'Authorization': f"Bearer {param.access_token}",
        }

        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        kubeconfig = response.text
        # Save kubeconfig to a temporary file
        config_path = "/tmp/kubeconfig.yaml"
        with open(config_path, 'w') as file:
            file.write(kubeconfig)
        
        return config_path  # Return the temporary file path

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching kubeconfig: {e}")

def get_registration_command(rancher_url: str, access_token: str, cluster_id: str, role: str) -> str:
    try:
        url = f"{rancher_url}/clusters/{cluster_id}/clusterRegistrationTokens"
        headers = {
            'Authorization': f"Bearer {access_token}",
        }

        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        registration_command = response.json()['data'][0]['nodeCommand']

        if role == 'master':
            return f"{registration_command} --etcd --controlplane"
        elif role == 'worker':
            return registration_command
        else:
            raise ValueError('Invalid role specified. Use "master" or "worker".')

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching registration command: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")

def execute_remote_command(ip: str, username: str, password: str, command: str) -> str:
    try:
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=username, password=password)
        
        stdin, stdout, stderr = client.exec_command(command)
        
        output = stdout.read().decode()
        error = stderr.read().decode()

        client.close()

        if error:
            raise HTTPException(status_code=500, detail=f"Error executing remote command: {error}")

        return output

    except paramiko.SSHException as e:
        raise HTTPException(status_code=500, detail=f"SSH connection error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing remote command: {e}")

def upload_file_to_master(ip: str, username: str, password: str, local_path: str, remote_path: str) -> None:
    try:
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        with SCPClient(ssh.get_transport()) as scp:
            scp.put(local_path, remote_path)  # Upload the file

        ssh.close()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {e}")

def create_remote_directory(ip: str, username: str, password: str, remote_path: str) -> None:
    command = f"mkdir -p {remote_path}"
    execute_remote_command(ip, username, password, command)

@app.post("/join_node/")
def join_node(params: Kubeparam = Body(...)):
    command = get_registration_command(params.rancher_url, params.access_token, params.cluster_id, params.role)
    output = execute_remote_command(params.ipdestinantion, params.username, params.password, command)
    
    # Fetch the kubeconfig file and upload it
    kubeconfig_path = get_kubeconfig(params)
    remote_path = f"/{params.useraccount}/.kube/config"
    create_remote_directory(params.ipdestinantion, params.username, params.password, "/".join(remote_path.split("/")[:-1]))  # Create the .kube directory
    upload_file_to_master(params.ipdestinantion, params.username, params.password, kubeconfig_path, remote_path)

    return {"message": "Node successfully joined to the cluster.", "output": output}

@app.get("/fetch_kubeconfig/")
def fetch_kubeconfig(params: Kubeparam = Body(...)):
    file_path = get_kubeconfig(params)
    return {"message": "Kubeconfig fetched successfully.", "file": file_path}
