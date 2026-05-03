import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT')

# Notion Settings
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
    "AI_Agents",
    "artificial",
    "ArtificialInteligence",
    "OpenAI",
    "ClaudeAI",
    "PromptEngineering"
]

# Summarization Settings
MAX_TOKENS = 1000
TEMPERATURE = 0.7
