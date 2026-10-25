# Grantový agent Sláva Volklore

Každý druhý den ráno projde zdroje s výzvami a grantovými newslettery, vybere, co sedí na Sláva Volklore, a pošle jeden souhrnný e-mail na slavavolkloreagent@gmail.com.

## Kde co měnit (bez programování)

| Co | Soubor |
|---|---|
| Zdroje (weby, newslettery) | `config/sources.yaml` – přidat, smazat nebo `enabled: false` |
| Jak často a v kolik | `config/settings.yaml` → `schedule` |
| Komu se posílá | `config/settings.yaml` → `email.to` |
| Právní forma žadatele | `config/settings.yaml` → `organization` |
| Jak agent hodnotí a píše | `config/prompts/*.md` |

Úprava na GitHubu: otevřít soubor → ikonka tužky → změnit → **Commit changes**.

## Tajné údaje (GitHub → Settings → Secrets and variables → Actions)

| Název | Co tam patří |
|---|---|
| `OPENAI_API_KEY` | klíč z platform.openai.com |
| `SUPABASE_URL` | `https://<projekt>.supabase.co` (bez `/rest/v1`) |
| `SUPABASE_KEY` | secret klíč ze Supabase (Project Settings → API Keys) |
| `RESEND_API_KEY` | klíč z resend.com (registrace e-mailem slavavolkloreagent@gmail.com) |

## Ruční spuštění

GitHub → **Actions** → **Grantový agent** → **Run workflow** → vybrat režim → **Run workflow**. Po doběhnutí kliknout na běh → `run` → rozbalit kroky a přečíst log. Souhrn je na konci.

## Čas

Cron na GitHubu běží v UTC a GitHub plánované běhy často zpožďuje, někdy i o hodiny. Proto jsou nastavené čtyři pokusy (5:30, 6:30, 7:30 a 8:30 UTC). Skript pošle e-mail při prvním z nich, který spadne do okna 7:00–11:59 v Praze (`send_hour` až `send_until_hour`), a další ten den přeskočí, protože v tabulce `runs` vidí, že už se poslalo. Přepínat letní a zimní čas není potřeba.
