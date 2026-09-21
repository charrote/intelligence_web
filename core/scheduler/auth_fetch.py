"""Multi-type authenticated fetching for datasource auth.

Supports auth_type: basic / bearer / cookie / form_login.

Used by the search cycle when a Tavily result URL matches a datasource that
carries credentials (matched by hostname, see core.datasource.match_auth).
Design: best-effort — on any failure the caller falls back to the
unauthenticated behavior (Tavily snippet). Login results are cached per
source to avoid re-logging-in every tick and to back off after failures
(protects accounts from lockout loops). Credentials are never logged.
"""

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = 20

# 登录结果缓存：(host, auth_type, username) -> {'session', 'ok_at', 'fail_at'}
_login_cache = {}
_SESSION_TTL = 12 * 3600   # 登录成功后 12h 内复用会话
_FAIL_BACKOFF = 6 * 3600   # 登录失败后 6h 内不重试（防账号风控/锁定循环）


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers['User-Agent'] = _UA
    s.headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
    return s


def build_session(auth: dict) -> requests.Session:
    """Build a session for basic/bearer/cookie (no network I/O)."""
    s = _new_session()
    t = auth['auth_type']
    if t == 'basic':
        s.auth = (auth.get('username') or '', auth.get('password') or '')
    elif t == 'bearer':
        s.headers['Authorization'] = 'Bearer ' + (auth.get('password') or '')
    elif t == 'cookie':
        s.headers['Cookie'] = auth.get('password') or ''
    return s


def _find_login_form(soup):
    """Locate the login form: first <form> containing a password input.

    Returns (form, username_input, password_input) or (None, None, None).
    Username field is picked by name heuristic (user/email/mail/account/
    login/name), else the first text-like input.
    """
    for form in soup.find_all('form'):
        pw = form.find('input', {'type': 'password'})
        if not pw:
            continue
        uname = None
        for inp in form.find_all('input'):
            itype = (inp.get('type') or 'text').lower()
            if itype in ('hidden', 'submit', 'button', 'image', 'checkbox', 'radio', 'file', 'password'):
                continue
            name = (inp.get('name') or '').lower()
            if any(k in name for k in ('user', 'email', 'mail', 'account', 'login', 'name')):
                uname = inp
                break
        if uname is None:
            uname = form.find('input', {'type': re.compile('^(text|email|tel)$', re.I)}) \
                or form.find('input')
        return form, uname, pw
    return None, None, None


def form_login(session, login_url, username, password) -> bool:
    """Generic best-effort HTML form login. Returns True on success.

    Success heuristic: POST accepted (<400) and the final page no longer
    contains a password input (i.e. the login form is gone). JS-rendered
    login pages, CAPTCHA and 2FA are out of scope by design.
    """
    try:
        resp = session.get(login_url, timeout=_TIMEOUT)
        if resp.status_code in (401, 403):
            return False
        soup = BeautifulSoup(resp.text, 'lxml')
        form, uname, pw = _find_login_form(soup)
        if form is None:
            return False
        data = {}
        for inp in form.find_all('input'):
            itype = (inp.get('type') or 'text').lower()
            if itype in ('submit', 'button', 'image'):
                continue
            name = inp.get('name')
            if not name:
                continue
            if inp is pw:
                data[name] = password
            elif inp is uname:
                data[name] = username
            else:
                data[name] = inp.get('value') or ''
        for sel in form.find_all('select'):
            name = sel.get('name')
            if not name:
                continue
            opt = sel.find('option', selected=True) or sel.find('option')
            data[name] = (opt.get('value', '') if opt else '')
        action = form.get('action') or login_url
        post = session.post(
            urljoin(login_url, action),
            data=data,
            timeout=_TIMEOUT,
            allow_redirects=True,
        )
        if post.status_code >= 400:
            return False
        after = BeautifulSoup(post.text, 'lxml')
        return after.find('input', {'type': 'password'}) is None
    except Exception as e:
        logger.warning(f"[auth_fetch] form login failed for {login_url[:80]}: {e}")
        return False


def get_authed_session(auth: dict):
    """Return (session, ok) with login-result caching.

    basic/bearer/cookie: fresh stateless session, always ok.
    form_login: reuses a successful login for _SESSION_TTL; after a failure
    retries are suppressed for _FAIL_BACKOFF.
    """
    login_url = auth.get('login_url') or ''
    host = urlparse(login_url).hostname or ''
    if auth['auth_type'] != 'form_login':
        return build_session(auth), True

    key = (host, auth['auth_type'], auth.get('username') or '')
    now = time.time()
    entry = _login_cache.get(key)
    if entry and entry.get('ok_at') and now - entry['ok_at'] < _SESSION_TTL:
        return entry['session'], True
    if entry and entry.get('fail_at') and now - entry['fail_at'] < _FAIL_BACKOFF:
        return None, False

    session = _new_session()
    ok = form_login(session, login_url, auth.get('username') or '', auth.get('password') or '')
    _login_cache[key] = {
        'session': session if ok else None,
        'ok_at': now if ok else None,
        'fail_at': None if ok else now,
    }
    if ok:
        logger.info(f"[auth_fetch] form login ok: {host}")
    else:
        logger.warning(f"[auth_fetch] form login failed: {host} (backoff 6h)")
    return (session, True) if ok else (None, False)


def fetch_url(url: str, auth: dict):
    """Fetch a URL using the datasource auth. Returns (html_text, ok).

    ok=False means the caller should fall back (e.g. Tavily snippet).
    html_text is raw page HTML — article extraction is the caller's job.
    Never logs credentials.
    """
    try:
        session, ok = get_authed_session(auth)
        if not ok:
            return '', False
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return '', False
        return resp.text, True
    except Exception as e:
        logger.warning(f"[auth_fetch] fetch failed for {url[:80]}: {e}")
        return '', False
