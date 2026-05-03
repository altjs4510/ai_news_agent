import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT')

# Notion Settings (NotionWriter reads NOTION_TOKEN / NOTION_DATABASE_ID directly via os.getenv)
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

# News Sources
AI_TIMES_URL = "https://www.aitimes.com"
AI_TIMES_BASE = "https://www.aitimes.com"

YOUTUBE_CHANNELS = {
    "안될공학": "UCeN2YeJcBCRJoXgzF_OU3qw",
    "조코딩": "UCQNE2JmbasNYbjGAcuBiRRg",
    "필로소피 AI 교육": "UCKXP5U8mn3UMC6gWblROxAA"
}

REDDIT_SUBREDDITS = [
    # 일반 AI 동향
    "artificial",
    "ArtificialInteligence",
    "OpenAI",
    "ClaudeAI",
    "PromptEngineering",
    # 에이전트·MCP·로컬 LLM 본진 (DCSAI / Team Agent 키워드 매칭)
    "AI_Agents",
    "LocalLLaMA",
    "mcp",
    "LangChain",
    "MachineLearning",
    # 코딩 에이전트 패턴 비교 (Claude Code plugin/skill/hook 학습용)
    "cursor",
    "ChatGPTCoding",
]

# Summarization Settings
MAX_TOKENS = 1000
TEMPERATURE = 0.7
