#!/usr/bin/env python
"""
微信公众号 API 测试脚本

用于验证微信公众号凭证是否正确配置。
"""
import asyncio
import httpx
import json
from datetime import datetime


# 微信公众号凭证
APP_ID = "wx756a64cb5127a7b5"
APP_SECRET = "e2075f234a5d919e66d88cde89ade740"


async def get_access_token():
    """获取微信 Access Token"""
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": APP_ID,
        "secret": APP_SECRET
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        return response.json()


async def get_api_permissions(token):
    """获取公众号的 API 权限信息"""
    url = "https://api.weixin.qq.com/cgi-bin/get_api_domain_ip"
    params = {"access_token": token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        return response.json()


async def get_account_basic_info(token):
    """获取公众号基本信息"""
    url = "https://api.weixin.qq.com/cgi-bin/account/getaccountbasicinfo"
    params = {"access_token": token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        return response.json()


async def test_draft_api(token):
    """测试草稿 API"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/count"
    params = {"access_token": token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        return response.json()


async def main():
    print("=" * 60)
    print("微信公众号 API 连接测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print(f"\n📋 AppID: {APP_ID}")
    print(f"📋 AppSecret: {APP_SECRET[:10]}...{APP_SECRET[-6:]}")

    # 1. 测试获取 Access Token
    print("\n" + "-" * 40)
    print("1️⃣ 测试获取 Access Token...")
    print("-" * 40)

    try:
        token_result = await get_access_token()

        if "access_token" in token_result:
            access_token = token_result["access_token"]
            expires_in = token_result.get("expires_in", 7200)
            print(f"✅ Access Token 获取成功!")
            print(f"   Token: {access_token[:30]}...")
            print(f"   有效期: {expires_in} 秒 ({expires_in // 3600} 小时)")

        elif "errcode" in token_result:
            errcode = token_result["errcode"]
            errmsg = token_result.get("errmsg", "未知错误")
            print(f"❌ 获取 Access Token 失败!")
            print(f"   错误码: {errcode}")
            print(f"   错误信息: {errmsg}")

            # 常见错误码说明
            error_desc = {
                40001: "AppSecret 错误或不属于该公众号",
                40002: "请确保 grant_type 为 client_credential",
                40013: "AppID 无效",
                40163: "AppSecret 已被使用过，请检查是否泄露",
            }
            if errcode in error_desc:
                print(f"   可能原因: {error_desc[errcode]}")
            return
        else:
            print(f"⚠️ 未知响应: {token_result}")
            return

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return

    # 2. 测试 API 权限
    print("\n" + "-" * 40)
    print("2️⃣ 测试 API 权限...")
    print("-" * 40)

    try:
        ip_result = await get_api_permissions(access_token)
        if "ip_list" in ip_result:
            print(f"✅ API 权限正常")
            print(f"   允许的 IP 数量: {len(ip_result['ip_list'])}")
        else:
            print(f"⚠️ API 权限检查: {ip_result}")
    except Exception as e:
        print(f"⚠️ API 权限检查失败: {e}")

    # 3. 测试公众号基本信息
    print("\n" + "-" * 40)
    print("3️⃣ 获取公众号基本信息...")
    print("-" * 40)

    try:
        info_result = await get_account_basic_info(access_token)
        if "nickname" in info_result:
            print(f"✅ 公众号名称: {info_result['nickname']}")
            print(f"   公众号类型: {info_result.get('service_type', {}).get('name', '未知')}")
            print(f"   认证状态: {'已认证' if info_result.get('verify_type', {}).get('id', -1) >= 0 else '未认证'}")
        elif "errcode" in info_result:
            print(f"⚠️ 获取基本信息: 错误码 {info_result['errcode']}")
        else:
            print(f"⚠️ 基本信息响应: {info_result}")
    except Exception as e:
        print(f"⚠️ 获取基本信息失败: {e}")

    # 4. 测试草稿 API
    print("\n" + "-" * 40)
    print("4️⃣ 测试草稿 API...")
    print("-" * 40)

    try:
        draft_result = await test_draft_api(access_token)
        if "total_count" in draft_result:
            print(f"✅ 草稿 API 可用")
            print(f"   当前草稿数量: {draft_result['total_count']}")
        elif "errcode" in draft_result:
            errcode = draft_result["errcode"]
            errmsg = draft_result.get("errmsg", "")
            if errcode == 45009:
                print(f"⚠️ 草稿 API 需要服务号权限")
            else:
                print(f"⚠️ 草稿 API 错误: {errcode} - {errmsg}")
        else:
            print(f"⚠️ 草稿 API 响应: {draft_result}")
    except Exception as e:
        print(f"⚠️ 草稿 API 测试失败: {e}")

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print("""
✅ 如果 Access Token 获取成功，说明凭证配置正确

📌 对于订阅号:
   - 可以使用草稿 API 创建图文消息
   - 发布需要手动在公众号后台操作

📌 对于服务号:
   - 可以直接通过 API 发布文章
   - 支持更多高级功能
""")

    return access_token


if __name__ == "__main__":
    asyncio.run(main())