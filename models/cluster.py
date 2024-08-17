from pydantic import BaseModel


class ClusterRequest(BaseModel):
    cluster_name: str
    kubernetes_version: str
    rancher_url: str
    access_token: str