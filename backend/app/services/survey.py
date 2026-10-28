"""Pesquisa: o que a população precisa para acompanhar a vida política.

Opcional e ligada à conta (nunca é condição para usar o app). Convite logo após o cadastro;
quem dispensar vê um lembrete uma única vez, alguns dias depois.

Fonte única das perguntas: a página /pesquisa monta o formulário a partir daqui e a API
valida as respostas contra esta definição. Para mudar uma pergunta, edite só este arquivo.
Os ids (de pergunta e de opção) são o que fica gravado; mude o texto à vontade, mas não
reaproveite um id com outro sentido, senão o resumo mistura respostas diferentes.

Por LGPD, a pesquisa não pergunta partido, voto ou posição política.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

SURVEY_VERSION = 1

QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "frequencia",
        "text": "Com que frequência você acompanha o que seus deputados e senadores fazem?",
        "kind": "single",
        "options": [
            ("nunca", "Nunca acompanho"),
            ("eleicao", "Só em época de eleição"),
            ("mensal", "De vez em quando, algumas vezes por mês"),
            ("semanal", "Toda semana"),
            ("diario", "Todo dia"),
        ],
    },
    {
        "id": "fontes",
        "text": "Onde você costuma se informar sobre política hoje?",
        "kind": "multi",
        "options": [
            ("tv_radio", "TV ou rádio"),
            ("sites", "Sites e jornais"),
            ("redes", "Instagram, TikTok ou X"),
            ("mensageiros", "WhatsApp ou Telegram"),
            ("video", "YouTube ou podcasts"),
            ("oficiais", "Sites oficiais da Câmara e do Senado"),
            ("pessoas", "Conversas com amigos e família"),
            ("nenhum", "Não costumo me informar"),
        ],
    },
    {
        "id": "barreiras",
        "text": "O que mais atrapalha você a acompanhar a política?",
        "kind": "multi",
        "max": 3,
        "options": [
            ("linguagem", "A linguagem é difícil de entender"),
            ("tempo", "Falta de tempo"),
            ("onde", "Não sei onde procurar"),
            ("espalhado", "A informação está espalhada em muitos lugares"),
            ("confianca", "Não confio nas fontes ou tenho medo de fake news"),
            ("impacto", "Não vejo como isso afeta a minha vida"),
            ("brigas", "As discussões são muito polarizadas e cansativas"),
        ],
    },
    {
        "id": "interesses",
        "text": "O que você mais gostaria de saber sobre seus representantes?",
        "kind": "multi",
        "max": 3,
        "options": [
            ("votos", "Como votam nos projetos"),
            ("presenca", "Se estão comparecendo às sessões"),
            ("gastos", "Quanto e como gastam a cota parlamentar"),
            ("projetos", "Que projetos apresentam"),
            ("agenda", "Agenda e compromissos"),
            ("temas", "O que pensam sobre os temas que me importam"),
            ("promessas", "Se cumprem o que prometeram na campanha"),
            ("noticias", "Notícias sobre eles"),
        ],
    },
    {
        "id": "temas",
        "text": "Quais temas mais interessam a você?",
        "kind": "multi",
        "max": 3,
        "options": [
            ("saude", "Saúde"),
            ("educacao", "Educação"),
            ("seguranca", "Segurança pública"),
            ("economia", "Economia e emprego"),
            ("impostos", "Impostos"),
            ("meio_ambiente", "Meio ambiente"),
            ("transporte", "Transporte e mobilidade"),
            ("moradia", "Moradia"),
            ("direitos", "Direitos e igualdade"),
            ("transparencia", "Combate à corrupção e transparência"),
            ("agro", "Agronegócio"),
            ("tecnologia", "Tecnologia e internet"),
        ],
    },
    {
        "id": "formato",
        "text": "Como você prefere receber as informações?",
        "kind": "multi",
        "max": 2,
        "options": [
            ("resumo", "Resumo curto em linguagem simples"),
            ("numeros", "Números e gráficos"),
            ("video", "Vídeos curtos"),
            ("completo", "Texto completo, com as fontes oficiais"),
        ],
    },
    {
        "id": "canal",
        "text": "Por onde você gostaria de receber as novidades?",
        "kind": "multi",
        "max": 2,
        "options": [
            ("app", "Notificação no app"),
            ("email", "E-mail semanal"),
            ("whatsapp", "WhatsApp"),
            ("abrir", "Prefiro abrir o app quando quiser"),
        ],
    },
    {
        "id": "voz",
        "text": "Você gostaria de dizer aos seus representantes o que pensa sobre os projetos?",
        "kind": "single",
        "options": [
            ("sim", "Sim, gostaria muito"),
            ("talvez", "Talvez, se fosse fácil"),
            ("nao", "Não tenho interesse"),
        ],
    },
    {
        "id": "idade",
        "text": "Qual a sua faixa etária?",
        "kind": "single",
        "options": [
            ("16-24", "16 a 24 anos"),
            ("25-34", "25 a 34 anos"),
            ("35-44", "35 a 44 anos"),
            ("45-59", "45 a 59 anos"),
            ("60+", "60 anos ou mais"),
        ],
    },
    {
        "id": "aberta",
        "text": "O que faria você acompanhar mais a política? (opcional)",
        "kind": "text",
        "max_length": 500,
    },
]

_BY_ID = {q["id"]: q for q in QUESTIONS}


class SurveyError(ValueError):
    pass


def public_survey() -> dict[str, Any]:
    """Definição para o frontend montar o formulário."""
    return {
        "version": SURVEY_VERSION,
        "questions": [
            {
                "id": q["id"],
                "text": q["text"],
                "kind": q["kind"],
                "max": q.get("max"),
                "max_length": q.get("max_length"),
                "options": [{"id": oid, "label": label} for oid, label in q.get("options", [])],
            }
            for q in QUESTIONS
        ],
    }


def clean_answers(raw: dict[str, Any]) -> dict[str, Any]:
    """Valida as respostas contra a definição; todas as perguntas são opcionais."""
    out: dict[str, Any] = {}
    for qid, value in (raw or {}).items():
        q = _BY_ID.get(qid)
        if q is None:
            raise SurveyError(f"Pergunta desconhecida: {qid}")
        if value in (None, "", []):
            continue
        if q["kind"] == "text":
            if not isinstance(value, str):
                raise SurveyError(f"Resposta inválida em {qid}")
            text = " ".join(value.split())[: q["max_length"]]
            if text:
                out[qid] = text
            continue
        valid = {oid for oid, _ in q["options"]}
        chosen = [value] if isinstance(value, str) else value
        if not isinstance(chosen, list) or not all(isinstance(v, str) for v in chosen):
            raise SurveyError(f"Resposta inválida em {qid}")
        chosen = list(dict.fromkeys(chosen))  # sem repetir, mantendo a ordem
        if any(v not in valid for v in chosen):
            raise SurveyError(f"Opção inválida em {qid}")
        if q["kind"] == "single" and len(chosen) > 1:
            raise SurveyError(f"Escolha só uma opção em {qid}")
        if q.get("max") and len(chosen) > q["max"]:
            raise SurveyError(f"Escolha até {q['max']} opções em {qid}")
        out[qid] = chosen[0] if q["kind"] == "single" else chosen
    return out


def summarize(answers_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Contagem por opção de cada pergunta fechada; abertas vão à parte."""
    result = []
    for q in QUESTIONS:
        if q["kind"] == "text":
            continue
        counts = {oid: 0 for oid, _ in q["options"]}
        answered = 0
        for a in answers_list:
            v = a.get(q["id"])
            if v is None:
                continue
            answered += 1
            for oid in [v] if isinstance(v, str) else v:
                if oid in counts:
                    counts[oid] += 1
        result.append(
            {
                "id": q["id"],
                "text": q["text"],
                "kind": q["kind"],
                "answered": answered,
                "options": [
                    {"id": oid, "label": label, "count": counts[oid]} for oid, label in q["options"]
                ],
            }
        )
    return result


REMIND_AFTER_DAYS = 3


def prompt_state(
    exists: bool,
    completed_at: datetime | None,
    dismissed_at: datetime | None,
    reminded_at: datetime | None,
    now: datetime,
) -> dict[str, bool]:
    """Quando convidar a responder.

    ``prompt``: primeira vez (nunca respondeu nem dispensou).
    ``remind``: uma única vez, REMIND_AFTER_DAYS dias depois do "Agora não".
    """
    if completed_at is not None:
        return {"prompt": False, "remind": False}
    if not exists or dismissed_at is None:
        return {"prompt": True, "remind": False}
    due = now - dismissed_at >= timedelta(days=REMIND_AFTER_DAYS)
    return {"prompt": False, "remind": due and reminded_at is None}
