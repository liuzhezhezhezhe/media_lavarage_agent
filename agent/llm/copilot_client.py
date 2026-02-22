"""GitHub Copilot LLM client via device flow (non-official, ToS gray area)."""
import time
from pathlib import Path

import httpx
from dotenv import set_key
from openai import AsyncOpenAI
from agent.llm.base import LLMClient, LLMResponse

_ENV_FILE = Path(".env")
_COPILOT_CHAT_URL_DEFAULT = "https://api.individual.githubcopilot.com"
_GH_CLIENT_ID = "Iv1.b507a08c87ecfe98"  # public VSCode extension client ID
_TOKEN_TTL = 25 * 60  # 25 min in seconds
_REFRESH_BEFORE = 60   # refresh 60 s before expiry

# Required by the Copilot API — identifies the integration type.
# Without this header the chat endpoint returns 400/401.
_COPILOT_HEADERS = {
    "Copilot-Integration-Id": "vscode-chat",
    "Editor-Version": "vscode/1.95.0",
    "Editor-Plugin-Version": "copilot-chat/0.22.4",
}


class CopilotClient(LLMClient):
    def __init__(self, github_token: str, model: str):
        self._github_token = github_token
        self._model = model
        self._copilot_token: str | None = None
        self._copilot_base_url: str = _COPILOT_CHAT_URL_DEFAULT
        self._token_expires_at: float = 0.0

    # ── device flow (called once at startup from main) ────────────────────────

    @staticmethod
    def run_device_flow() -> str:
        """Interactive terminal device flow.

        On success, writes GITHUB_TOKEN back to .env so subsequent runs
        skip the device flow entirely.
        """
        print("\n=== GitHub Copilot Device Flow ===")
        with httpx.Client() as client:
            r = client.post(
                "https://github.com/login/device/code",
                json={"client_id": _GH_CLIENT_ID, "scope": "read:user"},
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            data = r.json()

        device_code = data["device_code"]
        interval = data.get("interval", 5)
        print(f"Visit: {data['verification_uri']}")
        print(f"Enter code: {data['user_code']}")
        print("Waiting for authorization...")

        with httpx.Client() as client:
            while True:
                time.sleep(interval)
                poll = client.post(
                    "https://github.com/login/oauth/access_token",
                    json={
                        "client_id": _GH_CLIENT_ID,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Accept": "application/json"},
                )
                pd = poll.json()
                if "access_token" in pd:
                    token = pd["access_token"]
                    # Persist to .env so next startup skips device flow
                    if _ENV_FILE.exists():
                        set_key(str(_ENV_FILE), "GITHUB_TOKEN", token)
                        print(f"Token saved to {_ENV_FILE} (GITHUB_TOKEN).")
                    else:
                        print(f"Warning: {_ENV_FILE} not found, token not persisted.")
                        print(f"Add to your .env:  GITHUB_TOKEN={token}")
                    return token
                err = pd.get("error", "")
                if err == "authorization_pending":
                    continue
                elif err == "slow_down":
                    interval += 5
                else:
                    raise RuntimeError(f"Device flow failed: {pd}")

    # ── copilot token refresh ─────────────────────────────────────────────────

    async def _ensure_copilot_token(self) -> str:
        now = time.time()
        if self._copilot_token and now < self._token_expires_at - _REFRESH_BEFORE:
            return self._copilot_token

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                "https://api.github.com/copilot_internal/v2/token",
                headers={
                    "Authorization": f"token {self._github_token}",
                    "Accept": "application/json",
                    "Editor-Version": "vscode/1.95.0",
                    "Editor-Plugin-Version": "copilot-chat/0.22.4",
                    "Copilot-Integration-Id": "vscode-chat",
                    "User-Agent": "GithubCopilot/1.246.0",
                    "X-GitHub-Api-Version": "2023-01-01",
                },
            )
            r.raise_for_status()
            data = r.json()

        raw_token: str = data["token"]

        # Prefer the structured endpoints field; fall back to default.
        # Note: the "proxy-ep" field in the token string is a bare hostname
        # without scheme, so it cannot be used directly as a base URL.
        base_url = (
            data.get("endpoints", {}).get("api") or _COPILOT_CHAT_URL_DEFAULT
        )
        self._copilot_base_url = base_url

        self._copilot_token = raw_token
        self._token_expires_at = data.get("expires_at", now + _TOKEN_TTL)
        return self._copilot_token

    # ── complete ──────────────────────────────────────────────────────────────

    async def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> LLMResponse:
        token = await self._ensure_copilot_token()
        client = AsyncOpenAI(
            api_key=token,
            base_url=self._copilot_base_url,
            default_headers=_COPILOT_HEADERS,
        )
        resp = await client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}] + messages,
        )
        content = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return LLMResponse(content=content, tokens_used=tokens, model=self._model)

    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        token = await self._ensure_copilot_token()
        client = AsyncOpenAI(
            api_key=token,
            base_url=self._copilot_base_url,
            default_headers=_COPILOT_HEADERS,
        )
        resp = await client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return LLMResponse(content=content, tokens_used=tokens, model=self._model)
