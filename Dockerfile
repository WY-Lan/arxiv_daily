FROM python:3.11-slim

WORKDIR /app

# 使用阿里云 Debian 镜像源（国内服务器加速）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# 使用阿里云 PyPI 镜像加速 pip 安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# 复制项目代码
COPY . .

# 创建必要的目录
RUN mkdir -p logs storage

# 设置时区为上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 默认命令：启动定时任务
CMD ["python", "main.py", "schedule"]