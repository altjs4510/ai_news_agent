import os
import subprocess
from datetime import datetime
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger('blog_publisher')


class BlogPublisher:
    """수집·요약 결과를 별도 ai_news_blog 레포(Quartz)에 publish."""

    def __init__(self):
        default_path = str(Path(__file__).resolve().parent.parent.parent / "ai_news_blog")
        self.blog_repo = Path(os.getenv("BLOG_REPO_PATH", default_path)).resolve()
        self.posts_dir = self.blog_repo / "content" / "posts"
        self.site_url = os.getenv(
            "BLOG_SITE_URL", "https://altjs4510.github.io/ai_news_blog"
        ).rstrip("/")

    def publish(self, report_dir: str, date_str: str) -> str | None:
        if not self.blog_repo.is_dir():
            logger.error(f"블로그 레포를 찾을 수 없습니다: {self.blog_repo}")
            return None

        src = Path(report_dir)
        if not src.is_dir():
            logger.error(f"리포트 디렉토리가 없습니다: {report_dir}")
            return None

        target = self.posts_dir / date_str
        target.mkdir(parents=True, exist_ok=True)

        display_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

        copied = []
        for md in sorted(src.glob("*.md")):
            content = md.read_text(encoding="utf-8")
            if not content.lstrip().startswith("---"):
                title = md.stem.replace("_", " ").strip().capitalize()
                front = (
                    "---\n"
                    f'title: "{display_date} · {title}"\n'
                    f"date: {display_date}\n"
                    "---\n\n"
                )
                content = front + content
            (target / md.name).write_text(content, encoding="utf-8")
            copied.append(md.stem)

        if not copied:
            logger.warning("publish할 마크다운이 없습니다.")
            return None

        index = target / "index.md"
        if not index.exists():
            links = "\n".join(f"- [[{name}]]" for name in copied)
            index.write_text(
                "---\n"
                f'title: "{display_date} AI 동향"\n'
                f"date: {display_date}\n"
                "---\n\n"
                f"## 발행물\n\n{links}\n",
                encoding="utf-8",
            )

        if not self._git_commit_and_push(date_str):
            return None

        return f"{self.site_url}/posts/{date_str}/"

    def _git_commit_and_push(self, date_str: str) -> bool:
        try:
            subprocess.run(
                ["git", "-C", str(self.blog_repo), "add", "content/posts"],
                check=True,
                capture_output=True,
            )
            staged = subprocess.run(
                ["git", "-C", str(self.blog_repo), "diff", "--cached", "--quiet"]
            )
            if staged.returncode == 0:
                logger.info("블로그에 변경 사항이 없어 commit을 건너뜁니다.")
                return True
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.blog_repo),
                    "commit",
                    "-m",
                    f"chore: publish {date_str} digest",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(self.blog_repo), "push"],
                check=True,
                capture_output=True,
            )
            logger.info(f"블로그 publish 완료: {date_str}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            logger.error(f"git 동작 실패: {e} / {stderr}")
            return False
