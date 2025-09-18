#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
campus_autologin.py (macOS)
- 检测门户重定向（captive portal）
- 自动发现登录表单(action/隐藏字段)，带 Cookie/Referer 提交
- 从 Keychain 读取用户名/密码（service: campus_net_user / campus_net_pass）
- 失败重试 + 日志
"""

import os, sys, time, logging, subprocess, argparse
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# -------- 基本配置（一般不用改） --------
CHECK_URLS = ["http://clients3.google.com/generate_204", "http://captive.apple.com"]
SUCCESS_HINTS = [
    "success",
    "登录成功",
    "welcome",
    "logout",
    "/home",
    "上网已连接",
    "已在线",
]
LOGFILE = "/tmp/campus_autologin.log"
HTTP_TIMEOUT = 8
RETRY_MAX = 3
RETRY_BACKOFF = 4  # seconds
KC_USER_SVC = "campus_net_user"
KC_PASS_SVC = "campus_net_pass"

logging.basicConfig(
    filename=LOGFILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)


def read_keychain(service: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-s", service, "-w"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except subprocess.CalledProcessError:
        logging.error("Keychain read failed: %s", service)
        return None


def detect_captive() -> tuple[bool, str | None]:
    """返回 (是否被门户拦截, 门户URL或None)"""
    s = requests.Session()
    for url in CHECK_URLS:
        try:
            r = s.get(url, timeout=HTTP_TIMEOUT, allow_redirects=False)
            # 204 表示直连网络
            if r.status_code == 204:
                return False, None
            loc = r.headers.get("Location")
            if loc:
                return True, loc
            # 再试允许跳转，看有效URL是否改变
            r2 = s.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            if r2.url != url:
                return True, r2.url
            # 有些门户直接返回HTML登录页
            if "login" in (r.text or "").lower() or "<form" in (r.text or "").lower():
                return True, r.url
        except Exception as e:
            logging.warning("Connectivity check error on %s: %s", url, e)
            # 下一个 URL 继续
            continue
    # 全部失败时，保守认为可能有门户
    return True, None


def _guess_user_pass_names(form: BeautifulSoup) -> tuple[str | None, str | None]:
    uname = None
    pword = None
    for inp in form.find_all("input"):
        nm = (inp.get("name") or "").lower()
        tp = (inp.get("type") or "").lower()
        if not nm:
            continue
        if any(k in nm for k in ("user", "uname", "username", "account")) and not uname:
            uname = nm
        if tp == "password" or any(k in nm for k in ("pass", "pwd", "password")):
            if not pword:
                pword = nm
    return uname, pword


def build_form_payload(
    soup: BeautifulSoup, username: str, password: str
) -> tuple[str | None, dict]:
    """返回 (action_url, form_data)"""
    form = soup.find("form")
    if not form:
        return None, {}
    action = form.get("action")
    # 收集所有 input 默认值（包括隐藏 csrf）
    data = {}
    for inp in form.find_all("input"):
        nm = inp.get("name")
        if not nm:
            continue
        val = inp.get("value", "")
        data[nm] = val
    # 猜测用户名/密码字段名并填入
    uname, pword = _guess_user_pass_names(form)
    if uname:
        data[uname] = username
    if pword:
        data[pword] = password
    # 如果没猜出来，尝试常见组合
    if username not in data.values():
        for u, p in [
            ("username", "password"),
            ("user", "pass"),
            ("user", "pwd"),
            ("account", "password"),
        ]:
            if u not in data:
                data[u] = username
                data[p] = password
                break
    return action, data


def try_login(username: str, password: str, portal_url: str | None) -> bool:
    sess = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh) AutoLogin/1.0"}
    # 1) 先 GET 门户页（未知则直接试 CHECK_URLS 的有效重定向）
    page_url = portal_url
    if not page_url:
        page_url = CHECK_URLS[0]
    try:
        r = sess.get(
            page_url, headers=headers, timeout=HTTP_TIMEOUT, allow_redirects=True
        )
    except Exception as e:
        logging.warning("GET portal page fail: %s", e)
        r = None

    action_url = None
    payload = {}
    referer = None

    if r and r.ok:
        referer = r.url
        soup = BeautifulSoup(r.text or "", "lxml")
        act, payload = build_form_payload(soup, username, password)
        if act:
            action_url = urljoin(r.url, act)

    # 2) 如果没发现表单，就直接 POST 到当前地址（部分门户接受）
    if not action_url:
        action_url = referer or portal_url or CHECK_URLS[0]

    # 3) 提交
    try:
        r2 = sess.post(
            action_url,
            data=payload,
            headers={**headers, **({"Referer": referer} if referer else {})},
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
        body = (r2.text or "").lower()
        # 粗略判断成功
        if any(hint.lower() in body for hint in SUCCESS_HINTS):
            logging.info("Login success (hint matched) to %s", action_url)
            return True
        # 继续用 204/重定向方式判断是否已通
        captive, _ = detect_captive()
        if not captive:
            logging.info("Login success (no captive detected after POST)")
            return True
        logging.warning(
            "Login probably failed. status=%s url=%s", r2.status_code, r2.url
        )
        logging.debug("Resp snippet: %s", body[:1000])
        return False
    except Exception as e:
        logging.exception("POST login failed: %s", e)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--once", action="store_true", help="只运行一次（默认也只运行一次）"
    )
    ap.add_argument("--verbose", action="store_true", help="同时打印到控制台")
    args = ap.parse_args()

    if args.verbose:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(console)

    username = read_keychain(KC_USER_SVC)
    password = read_keychain(KC_PASS_SVC)
    if not username or not password:
        logging.error("Keychain 缺少凭据（campus_net_user / campus_net_pass）")
        return 2

    captive, portal = detect_captive()
    if not captive:
        logging.info("网络直连，无需登录。")
        return 0

    logging.info("检测到门户：%s", portal or "(未知入口)")

    for attempt in range(1, RETRY_MAX + 1):
        if try_login(username, password, portal_url=portal):
            logging.info("第 %d 次登录成功", attempt)
            return 0
        sleep = RETRY_BACKOFF * attempt
        logging.info("第 %d 次登录失败，%ds 后重试", attempt, sleep)
        time.sleep(sleep)

    logging.error("多次尝试仍失败。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
