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

BLUESKY_HANDLES = [
    # 2026-05 기준으로 실증 확인된 활성 AI 계정만 등록.
    # Karpathy / Anthropic / HF / DeepLearning.ai / Yann LeCun / Lilian Weng / swyx 등
    # 다수는 핸들을 squat했지만 X-only 운영이라 게시글이 0~소수에 그쳐 제외.
    # X-only 인물의 담론은 큐레이션 뉴스레터(TLDR AI / Rundown / AlphaSignal 등)가 24h 내 흡수.
    "simonwillison.net",
    "hardmaru.bsky.social",
    "emilymbender.bsky.social",
    "goodfellow.bsky.social",
    # 2026-05 시도: teknium1/nousresearch/karan4d 핸들 모두 "Profile not found".
    # Nous 진영은 여전히 X-only로 추정. GitHub topic 확장이 hermes-agent 캐치를
    # 대체로 커버하므로 Bluesky 사각지대는 후순위.
]

# X (Twitter) — 공식 API 대신 개인 계정 로그인 세션으로 Following 홈 타임라인을 읽는다.
# 이용약관상 자동 스크래핑 금지 행위라 계정 정지 리스크를 감수하는 경로 — 상세는 CLAUDE.md 참조.
# state 파일은 sources/x_login.py 를 1회 수동 실행해 발급(git-ignore, 세션 쿠키 포함).
X_STATE_PATH = "state/x_auth_state.json"
X_TIMELINE_LIMIT = 20

# 키워드 검색 — 팔로우 여부와 무관하게 바이럴/트렌드 게시물을 탐지.
# X 검색 연산자(since:/until:/min_faves:)로 서버 사이드에서 날짜·인게이지먼트 범위를 좁힌다.
# 특정 모델 버전명(GPT-5 등)은 넣지 않음 — 버전은 계속 바뀌고, 광범위한 주제어 + 인게이지먼트
# 기준만으로도 그 시점 화제(신규 모델 출시 등)가 자연히 상위로 걸러진다.
X_SEARCH_KEYWORDS = [
    "AI agent",
    "agentic AI",
    "LLM",
    "open weights",
    "AI coding assistant",
    "MCP protocol",
    "reasoning model",
    "AGI",
]
X_SEARCH_LIMIT_PER_KEYWORD = 8
X_SEARCH_MIN_FAVES = 200

# 키워드 트렌드 분석 — 일별 언급 횟수 누적(sources/x_trends.py)
X_TRENDS_STATE_PATH = "state/x_keyword_trends.json"

# 개인 계정이라 Following 피드에 기존 지인/취미 계정이 섞여 있음 — Bluesky와 동일하게
# 핸들 화이트리스트로 걸러서 AI 무관 게시물(연예/패션/스포츠 등)을 원천 차단한다.
# 2026-08 팔로우 시작. 대소문자 무시 매칭(x_timeline.py).
X_HANDLES = [
    # 공식 랩/기업
    "OpenAI", "AnthropicAI", "GoogleDeepMind", "AIatMeta", "MistralAI",
    "xai", "huggingface", "perplexity_ai",
    # 리서처/빌더 — Bluesky에 없는 X-only 인물(BLUESKY_HANDLES 주석 참조)
    "karpathy", "ylecun", "lilianweng", "DrJimFan", "AndrewYNg",
    "fchollet", "jeremyphoward", "rasbt", "_akhaliq", "polynoamial",
    "demishassabis",
    # 코딩 에이전트 / 개발 툴
    "swyx", "simonw", "AravSrinivas", "amasad", "cursor_ai", "LangChainAI",
    # 오픈소스 / 로컬 LLM
    "Teknium1", "NousResearch", "UnslothAI", "togethercompute",
    # AI 뉴스 큐레이션
    "rowancheung",
]

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
