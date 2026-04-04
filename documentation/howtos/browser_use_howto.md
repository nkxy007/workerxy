# Installing browser-use on CentOS Stream 10

## 1. System Dependencies

```bash
sudo dnf install -y python3.12 python3.12-pip git
```

## 2. Virtual Environment

```bash
python3.12 -m venv browseruse-env
source browseruse-env/bin/activate
```

## 3. Install browser-use

```bash
pip install browser-use
```

## 4. Install Playwright System Dependencies

Playwright's `--with-deps` flag does not work on CentOS (it assumes apt). Install manually:

```bash
sudo dnf install -y nss atk at-spi2-atk cups-libs libdrm libxkbcommon \
  libXcomposite libXdamage libXrandr mesa-libgbm pango alsa-lib \
  libX11 libXcursor libXext libXi libXtst gtk3
```

## 5. Install Playwright Chromium

```bash
playwright install chromium
```

## 6. Test Script

```python
import asyncio
import os
from browser_use import Agent, ChatOpenAI

async def main():
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=os.environ["OPENAI_API_KEY"],
    )
    agent = Agent(
        task="Go to google.com and return the page title",
        llm=llm,
    )
    result = await agent.run()
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
OPENAI_API_KEY=your-key-here python test_browseruse.py
```

---

## Notes

- `ChatOpenAI` must be imported from `browser_use`, not `langchain_openai` — newer versions of browser-use ship their own class and will throw an `AttributeError` otherwise.
- Playwright runs Chromium headless natively — no Xvfb needed.
- If Chromium still fails to launch, check for missing shared libraries: `ldd ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome | grep "not found"`