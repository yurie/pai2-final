"""Browser quiz where Ollama answers and the host judges the answer."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ament_index_python.packages import get_package_share_directory

from .pai2_final_quiz import OllamaClient, send_motion


MAX_BODY_SIZE = 16_384
AI_ERRORS = (OSError, TimeoutError, ValueError, TypeError, KeyError, json.JSONDecodeError)


class AIAnswerError(RuntimeError):
    pass


class QuizSession:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.ai = OllamaClient()
        self.question: str | None = None
        self.answer: str | None = None
        self.reason: str | None = None
        self.judgement: dict[str, Any] | None = None
        self.rounds = 0
        self.score = 0
        self.status = ''

    def ask(self, question: str) -> dict[str, Any]:
        question = question.strip()
        if not question:
            raise ValueError('問題を入力してください')
        if len(question) > 2000:
            raise ValueError('問題は2000文字以内にしてください')

        with self.lock:
            if self.answer is not None and self.judgement is None:
                raise ValueError('先にAIの回答を正解か不正解か判定してください')
            try:
                response = self.ai.answer_user_question(question)
            except AI_ERRORS as exc:
                raise AIAnswerError(str(exc)) from exc

            self.question = question
            self.answer = response['answer']
            self.reason = response['reason']
            self.judgement = None
            self.status = 'Ollamaが回答しました。正解か不正解かを選んでください。'
            return self.public_state()

    def judge(self, correct: bool) -> dict[str, Any]:
        if not isinstance(correct, bool):
            raise ValueError('判定は正解または不正解を選んでください')
        with self.lock:
            if self.answer is None or self.judgement is not None:
                raise ValueError('判定できるAI回答がありません')

            motion = 'celebrate' if correct else 'shake_no'
            motion_status = ''
            try:
                send_motion(motion)
            except (RuntimeError, OSError) as exc:
                motion_status = f'アーム動作を送信できませんでした: {exc}'

            self.rounds += 1
            if correct:
                self.score += 1
            self.judgement = {
                'correct': correct,
                'motion_status': motion_status,
            }
            self.status = '正解として記録しました。' if correct else '不正解として記録しました。'
            return self.public_state()

    def reset(self) -> dict[str, Any]:
        with self.lock:
            self.question = None
            self.answer = None
            self.reason = None
            self.judgement = None
            self.rounds = 0
            self.score = 0
            self.status = ''
            return self.public_state()

    def public_state(self) -> dict[str, Any]:
        return {
            'question': self.question,
            'answer': self.answer,
            'reason': self.reason,
            'judgement': self.judgement,
            'rounds': self.rounds,
            'score': self.score,
            'status': self.status,
            'can_ask': self.answer is None or self.judgement is not None,
        }


SESSION = QuizSession()


def _web_root() -> Path:
    try:
        return Path(get_package_share_directory('pai2_final')) / 'web'
    except Exception:
        return Path(__file__).resolve().parent.parent / 'web'


class QuizRequestHandler(BaseHTTPRequestHandler):
    server_version = 'PAI2Quiz/1.0'

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == '/':
            try:
                content = (_web_root() / 'index.html').read_bytes()
            except OSError:
                self.send_error(500, 'Web UIファイルを読み込めません')
                return
            self._send_json_or_bytes(200, content, 'text/html; charset=utf-8')
        elif path == '/api/state':
            with SESSION.lock:
                self._send_json(200, SESSION.public_state())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ('/api/ask', '/api/judge', '/api/reset'):
            self.send_error(404)
            return
        try:
            payload = self._read_json()
            if path == '/api/ask':
                state = SESSION.ask(str(payload.get('question', '')))
            elif path == '/api/reset':
                state = SESSION.reset()
            else:
                state = SESSION.judge(payload.get('correct'))
        except AIAnswerError as exc:
            self._send_json(503, {'error': f'Ollamaで回答を作成できませんでした: {exc}'})
            return
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json(400, {'error': str(exc)})
            return
        except (OSError, RuntimeError, TimeoutError, KeyError) as exc:
            self._send_json(503, {'error': f'OllamaまたはROSとの通信に失敗しました: {exc}'})
            return
        self._send_json(200, state)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0 or length > MAX_BODY_SIZE:
            raise ValueError('リクエストサイズが不正です')
        payload = json.loads(self.rfile.read(length).decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('JSONオブジェクトを送信してください')
        return payload

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self._send_json_or_bytes(status, content, 'application/json; charset=utf-8')

    def _send_json_or_bytes(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        print(f'[quiz-web] {self.address_string()} {format % args}')


def main() -> int:
    host = os.environ.get('WEB_HOST', '127.0.0.1')
    port = int(os.environ.get('WEB_PORT', '8000'))
    server = ThreadingHTTPServer((host, port), QuizRequestHandler)
    print(f'クイズ画面: http://{host}:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nWebクイズを終了します。')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
