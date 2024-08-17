from pydantic import BaseModel


class NodeParams(BaseModel):
    rancher_url: str
    access_token: str
    cluster_id: str
    role: str  # 'master' or 'worker'
    ip: str
    username: str
    password: str

    
class Kubeparam(BaseModel):
    rancher_url: str
    access_token: str
    cluster_id: str
    useraccount: str
    ipdestinantion: str
    role: str
    username: str
    password: str