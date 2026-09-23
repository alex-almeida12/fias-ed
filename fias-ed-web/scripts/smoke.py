#!/usr/bin/env python3
"""Teste de aceitação de ponta a ponta do FIAS-ED Web (W1) em http://localhost:8080.

Uso (de fias-ed-web/):  python scripts/smoke.py --admin-user pesquisador
A senha do admin é pedida no terminal (sem eco); se a entrada não for um terminal,
é lida da primeira linha do stdin. O script cria uma conta temporária de
professor, percorre o fluxo completo e exclui a conta no fim. A escola de teste
"Escola de teste (smoke)" fica no cadastro comum de escolas (é reaproveitada nas
execuções seguintes). Usa só a biblioteca padrão (o áudio de teste é gerado com
o módulo wave).
"""
import argparse
import getpass
import io
import json
import math
import struct
import sys
import time
import urllib.error
import urllib.request
import wave
from urllib.parse import quote

BASE = "http://localhost:8080"
ESCOLA_SMOKE = "Escola de teste (smoke)"
CABECALHOS = {
    "content-security-policy": "frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=()",
}


class Client:
    """Cliente HTTP com cookies próprios (o cookiejar não envia cookies Secure em http://localhost)."""

    def __init__(self):
        self.cookies: dict[str, str] = {}

    def request(self, method, path, body=None, raw=None, headers=None):
        h = dict(headers or {})
        if self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if method != "GET" and "fias_csrf" in self.cookies:
            h["X-CSRF-Token"] = self.cookies["fias_csrf"]
        data = raw
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - URL fixa local
                status, rh, payload = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, rh, payload = e.code, e.headers, e.read()
        for cookie in rh.get_all("Set-Cookie") or []:
            name, _, rest = cookie.partition("=")
            value = rest.split(";", 1)[0]
            if value and value != '""':
                self.cookies[name] = value
            else:
                self.cookies.pop(name, None)
        text = payload.decode("utf-8") if payload else ""
        is_json = (rh.get("Content-Type") or "").startswith("application/json")
        return status, rh, (json.loads(text) if text and is_json else text)


def wav_bytes(seconds=65, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(seconds * rate)))
    return buf.getvalue()


def check(cond, msg):
    if not cond:
        print(f"FALHOU: {msg}")
        sys.exit(1)
    print(f"ok  {msg}")


def step(resp, status, msg):
    code, _, body = resp
    check(code == status, f"{msg}" if code == status else f"{msg} — HTTP {code}: {body}")
    return body


# Este smoke é da W1: o que ele cobre é a validação do áudio, não o pipeline
# inteiro. Como AUDIO_VALIDATED deixou de ser ponto de parada (o handler já
# enfileira prepare_audio), esperar "fila vazia em AUDIO_VALIDATED" nunca mais
# aconteceria: a aula segue para PREPROCESSING logo em seguida. O smoke espera
# então o fim da validação — a aula sair dos estados anteriores a ela.
ANTES_DA_VALIDACAO = ("DRAFT", "AUDIO_IMPORTED")


def wait(client, aula_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        _, _, body = client.request("GET", f"/api/aulas/{aula_id}")
        if body.get("status") not in ANTES_DA_VALIDACAO:
            return body
        time.sleep(2)
    check(False, f"aula {aula_id} não terminou em {timeout}s")


def validou(body) -> bool:
    """O áudio passou pela validação: há linha de Audio e a aula não foi recusada.
    O status exato depende de quanto do pipeline já andou quando o smoke olhou."""
    return body.get("status") != "ERROR" and bool(body.get("audio"))


def escola(client):
    code, _, body = client.request("POST", "/api/escolas", {"name": ESCOLA_SMOKE})
    return body["duplicatas"][0]["id"] if code == 409 else step((code, None, body), 201, "escola criada")["id"]


def nova_aula(client, rotulo):
    turma = step(client.request("POST", "/api/turmas", {"name": f"Turma {rotulo}", "escola_id": escola(client)}), 201,
                 f"turma ({rotulo})")
    disc = step(client.request("POST", "/api/disciplinas", {"name": f"Disciplina {rotulo}"}), 201, f"disciplina ({rotulo})")
    return step(client.request("POST", "/api/aulas", {"turma_id": turma["id"], "disciplina_id": disc["id"],
                                                      "lesson_date": "2026-09-22"}), 201, f"aula ({rotulo})")["id"]


def enviar_e_processar(client, aula_id, nome, rotulo):
    step(client.request("PUT", f"/api/aulas/{aula_id}/audio", raw=wav_bytes(),
                        headers={"X-Filename": quote(nome), "Content-Type": "application/octet-stream"}),
         201, f"envio do áudio ({rotulo})")
    step(client.request("POST", f"/api/aulas/{aula_id}/processar"), 202, f"processamento solicitado ({rotulo})")
    return wait(client, aula_id)


def read_password(prompt):
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return sys.stdin.readline().rstrip("\r\n")


def main() -> int:
    sys.stdout.reconfigure(errors="replace")  # o console do Windows pode não ter todos os caracteres
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-user", required=True)
    args = ap.parse_args()
    admin_pw = read_password("Senha do administrador: ")

    code, headers, _ = Client().request("GET", "/")
    check(code == 200, "Home responde em http://localhost:8080")
    for name, fragment in CABECALHOS.items():
        check(fragment in (headers.get(name) or ""), f"cabeçalho {name}")

    admin = Client()
    step(admin.request("POST", "/api/auth/login", {"username": args.admin_user, "password": admin_pw}), 200, "admin entra")
    username = f"smoke{int(time.time())}"
    criada = step(admin.request("POST", "/api/admin/contas", {"username": username, "display_name": "Professora Teste"}),
                  201, "admin cria professor com senha provisória")
    prof_id, provisoria = criada["conta"]["id"], criada["senha_provisoria"]
    prof = Client()
    try:
        step(prof.request("POST", "/api/auth/login", {"username": username, "password": provisoria}), 200,
             "professor entra com a senha provisória")
        step(prof.request("GET", "/api/aulas"), 403, "senha provisória exige troca")
        step(prof.request("POST", "/api/auth/password", {"current_password": provisoria,
                                                          "new_password": "senha-do-smoke-123"}), 200, "professor troca a senha")

        body = enviar_e_processar(prof, nova_aula(prof, "smoke"), "aula teste.wav", "professor")
        check(validou(body), "áudio da aula é aceito na validação")

        body = enviar_e_processar(prof, nova_aula(prof, "extensão falsa"), "gravacao.mp3", "extensão falsa")
        check(body["status"] == "ERROR" and body["error_code"] == "AUDIO_FORMAT_MISMATCH" and body["error_message"],
              "extensão falsa termina em AUDIO_FORMAT_MISMATCH com mensagem humana")

        step(admin.request("POST", "/api/admin/agir-como", {"professor_id": prof_id}), 200, "admin age como o professor")
        feita = nova_aula(admin, "admin")
        body = enviar_e_processar(admin, feita, "aula do admin.wav", "admin")
        check(validou(body), "áudio da aula criada pelo admin é aceito na validação")
        step(admin.request("DELETE", "/api/admin/agir-como"), 200, "admin volta à própria conta")
        vista = step(prof.request("GET", f"/api/aulas/{feita}"), 200, "professor vê a aula criada pelo admin")
        check(bool(vista["alterada_pelo_admin_em"]), "aviso 'alterada pelo administrador' presente")
    finally:
        admin.request("DELETE", "/api/admin/agir-como")
        code, _, _ = admin.request("DELETE", f"/api/admin/contas/{prof_id}", {"confirmar_username": username})
        print("ok  conta temporária excluída" if code == 204 else f"ATENÇÃO: excluir a conta {username} manualmente (HTTP {code})")
    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
