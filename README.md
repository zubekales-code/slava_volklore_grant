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

Cron na GitHubu běží v UTC. Jsou nastavené dva běhy (5:30 a 6:30 UTC) a skript sám pustí jen ten, který odpovídá 7:30 v Praze. Přepínat letní a zimní čas proto není potřeba.
