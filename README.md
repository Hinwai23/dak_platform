# 基于 Airflow + Databricks 的本地数据平台

技术栈：

- **Airflow**：负责编排、调度、依赖管理
- **Databricks**：负责计算与数据建模
- **AWS S3**：作为原始数据落地层
- **Medallion**：分层建模



---

## 1）用处

目前能自动完成以下任务：

1. Airflow 定时下载 StackExchange 公共数据压缩包（`.7z`）
2. 解压得到 `Posts.xml` 和 `Users.xml`
3. 上传到 Amazon S3
4. 发布 Airflow 资产（`s3://.../raw/Posts.xml`、`s3://.../raw/Users.xml`）
5. 两个资产就绪后，触发 Databricks Workflow
6. Databricks Notebook 执行 Bronze/Silver/Gold 分层建模
7. Dashboard 消费 mart 表进行分析展示

---

## 2）整体架构

```text
+----------------------------+            +------------------------+
| 本地 K8s (kind)            |            | Databricks             |
|                            | trigger    |                        |
| Airflow DAGs               +----------->+ Workflow / Notebooks   |
| - produce_data_assets      |            | - bronze_*             |
| - trigger_databricks_*     |            | - silver_posts         |
+-------------+--------------+            | - gold_*               |
              |                           +-----------+------------+
              | 上传原始文件                           |
              v                                       | 写入数据表
+----------------------------+                        v
| S3 Raw Layer               |              +-----------------------+
| raw/Posts.xml              |              | Delta/Unity Catalog   |
| raw/Users.xml              |              | raw_users, raw_posts  |
+----------------------------+              | stg_posts             |
                                            | marts_*               |
                                            +-----------------------+
```

---

## 3）仓库结构

```text
.
├── dags/
│   ├── produce_data_assets.py
│   └── trigger_databricks_workflow_dag.py
├── notebooks/
│   ├── bronze_posts.ipynb
│   ├── bronze_users.ipynb
│   ├── bronze_posts_dqx.ipynb
│   ├── silver_posts.ipynb
│   ├── gold_most_popular_tags.ipynb
│   └── gold_posts_users.ipynb
├── chart/
│   ├── values-override.yaml
│   └── values-override-persistence.yaml
├── k8s/
│   ├── clusters/kind-cluster.yaml
│   └── volumes/
├── cicd/
│   └── Dockerfile
├── .github/workflows/cicd.yaml
├── install_airflow.sh
├── install_airflow_with_persistence.sh
├── install_airflow_with_ecr.sh
└── upgrade_airflow.sh
```

---

## 4）核心模块

### 4.1 Airflow DAG

- `produce_data_assets.py`
  - 按日从 Archive.org 下载数据
  - 解压 `.7z` 到 `/tmp`
  - 上传 `Posts.xml`、`Users.xml` 到 S3
  - 发布 Airflow 资产
- `trigger_databricks_workflow_dag.py`
  - 使用 `DatabricksRunNowOperator`
  - 以资产依赖为触发条件（两个资产均就绪）
  - 通过 `job_id` 触发 Databricks Job

### 4.2 Databricks Notebooks

- `bronze_posts.ipynb`、`bronze_users.ipynb`
  - XML 读取 + 显式 Schema
  - 列名标准化
  - 写入 raw 层表
- `bronze_posts_dqx.ipynb`
  - 使用 `databricks-labs-dqx` 做数据质量校验
  - 拆分有效数据与隔离数据（quarantine）
- `silver_posts.ipynb`
  - 标签拆分、字段映射、结构标准化
  - Delta merge 实现增量 upsert 到 `stg_posts`
- `gold_most_popular_tags.ipynb`
  - 产出热门标签聚合表
- `gold_posts_users.ipynb`
  - 产出帖子-用户宽表

### 4.3 部署方式

- 本地 `kind` 集群 + Helm 安装 Airflow（`apache-airflow/airflow`）
- 执行器：`KubernetesExecutor`
- 通过 `gitSync` 从 GitHub 同步 DAG
- 支持日志 PV/PVC 持久化（可选）

### 4.4 CI/CD

- 工作流文件：`.github/workflows/cicd.yaml`
- `main` 分支 push 后自动构建 Airflow 镜像并推送到 AWS ECR

---

## 5）环境准备

运行前请先安装：

- Docker
- kind
- kubectl
- Helm
- Databricks Workspace 与可执行 Job

Airflow 镜像中的 Python 依赖：

- `py7zr`
- `apache-airflow-providers-databricks`

---

## 6）本地部署

### 方案 A：标准安装

```bash
./install_airflow.sh
```

### 方案 B：带日志持久化安装

```bash
./install_airflow_with_persistence.sh
```

### 方案 C：从 ECR 拉取镜像并安装

```bash
./install_airflow_with_ecr.sh
```

安装后可通过端口转发访问 Airflow API/UI：

```bash
kubectl port-forward svc/airflow-api-server 8080:8080 --namespace airflow
```

---

## 7）必需配置

执行安装前，请完成以下配置：

1. **Kubernetes Git 凭证 Secret**
   - 默认路径：`k8s/secrets/git-secrets.yaml`
   - 已在 `.gitignore` 中排除

2. **Airflow Connection**
   - `aws_conn`： S3 名称
   - `databricks_conn`：调用 Databricks API

3. **Databricks Job**
   - 将 `dags/trigger_databricks_workflow_dag.py` 中的 `job_id` 替换为你自己的 Job ID

---


To generate your secrets for git sync, use base64 encoding, i.e.

“”“
echo -n 'your_github_classic_token_here' | base64
echo -n 'your_github_username_token_here' | base64
apiVersion: v1
kind: Secret
metadata:
  name: git-credentials
  namespace: airflow
data:
  GITSYNC_USERNAME: <base64 encoded user name here>
  GITSYNC_PASSWORD: <base64 encoded Git classic token here>
  GIT_SYNC_USERNAME: <base64 encoded user name here>
  GIT_SYNC_PASSWORD: <base64 encoded Git classic token here>
”“”

To enable CI/CD using github actions, set these two secret environment variables in your console:
“”“
---
- name: Configure AWS Creds
  uses: aws-actions/configure-aws-credentials@v2
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: us-east-1
”“”


## 8）运维

### 升级 Airflow 镜像与发布

```bash
./upgrade_airflow.sh
```

### 手动构建镜像

```bash
docker pull apache/airflow:3.1.8-python3.11
docker build --tag my-dags:<tag> -f cicd/Dockerfile .
```

---

## 9）常见问题

- **Airflow Pod 无法同步 DAG**
  - 检查 `gitSync` 的 repo/branch 配置与 secret 内容
- **Pod 重启后日志丢失**
  - 使用持久化安装脚本，并检查 PV/PVC 绑定状态
- **Databricks 任务触发即失败**
  - 检查 `databricks_conn` 与 `job_id` 是否正确
- **S3 上传失败**
  - 检查 `aws_conn` 权限与 bucket 配置
- **kind 挂载路径异常**
  - 检查 `k8s/clusters/kind-cluster.yaml` 中 hostPath 是否与本机系统一致

---

