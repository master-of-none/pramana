# Hermes on a VPS: a daily verse in your chat, with a free model

The plan: a small server runs **Pramana** (the texts) and **Hermes Agent** (the assistant) side
by side. You message Hermes on Telegram or WhatsApp ("send me something about fear"), and
Hermes also messages you every day on its own schedule. Hermes uses a free LLM provider, and
it remembers what you like. Pramana stays dumb on purpose: it returns one public-domain excerpt
per call and remembers nothing.

```
you ⇄ Telegram / WhatsApp ⇄ Hermes (LLM = a free provider) ──127.0.0.1──▶ Pramana (--agent-only)
                              └─ its own cron: "every day at 7:30 …"
```

Nothing is exposed except SSH. This builds on the [setup guide](agent-excerpts.md), which has
the details of the token, the routes and the cron alternative.

**Status:** the Pramana half (steps 1 to 3) was run here and on a real server; the Hermes,
Telegram and WhatsApp half (steps 4 to 8) is written from Hermes' official documentation and
**has not been run end to end**. Where I am not sure of a command I
say so.

## Choices made

| Question | Choice | Why |
| --- | --- | --- |
| Where do the daily messages come from? | **Hermes' own scheduler**, not plain cron | Hermes can learn your preferences and vary what it sends. |
| Which LLM? | **A free provider** | You accepted that it sees your chat. See [the limits](#the-free-model). |
| Which chat app? | **Telegram first, WhatsApp second** | Telegram needs only a bot token. Hermes' WhatsApp support is an unofficial bridge. |
| Where does Pramana run? | **On the same VPS, localhost only**, from a database built on your computer | No public port, no tunnel, no PyTorch on the server. |

## 1. Build a public-only library on your own computer

The server needs one file: a SQLite database holding **only** the public editions, with a
search index. Build it once, in a **new** folder (never copy your everyday `.pramana/`, which can
hold private books):

```sh
export PRAMANA_HOME=$HOME/pramana-public
# reuse what you already downloaded: the nine public editions the excerpt API may serve
for c in ashtavakra-richards sacred-texts-{brk,cjw,sbe01,sbe15,sbg,tmu,wos} vishnu-purana; do
  uv run pramana ingest ~/Programming/pramana/.pramana/corpora/$c/chapters.jsonl
done
ln -s ~/Programming/pramana/.pramana/models "$PRAMANA_HOME/models"   # your downloaded model
uv run pramana index                                                   # about 85 seconds here
```

(On a computer without those files: `uv run pramana corpus download --source excerpts` fetches
only those nine editions, `uv run pramana model setup` downloads the model once, then ingest
the files under `$PRAMANA_HOME/corpora/` and index. Those two commands are the repository's
existing ones; I did not re-run them for this guide.)

**Check it before you copy it.** It must be public-only:

```sh
python3 -c "
import sqlite3, json, sys
db = sqlite3.connect(sys.argv[1])
rows = [json.loads(d) for (d,) in db.execute('select data from chapters')]
private = [r['document_id'] for r in rows if r['source'].get('local_path')]
print(len(rows), 'chapters;', len({r['document_id'] for r in rows}), 'documents;', len(private), 'with a private local origin')
" "$PRAMANA_HOME/pramana.sqlite3"
```

Expect `591 chapters; 62 documents; 0 with a private local origin` and a 20 MB file. Anything else:
stop and do not copy it. (It has the index but not the model, so `topic` works by keywords only
on the server: see [below](#topic-search-on-the-server).)

## 2. Prepare the VPS

Examples assume Ubuntu or Debian; adjust for your system.

```sh
# as root, once
adduser --disabled-password --gecos "" pramana
mkdir -p /home/pramana/.ssh && cp ~/.ssh/authorized_keys /home/pramana/.ssh/
chown -R pramana:pramana /home/pramana/.ssh && chmod 700 /home/pramana/.ssh
apt update && apt install -y git curl ufw
ufw allow OpenSSH && ufw enable          # nothing else is opened
loginctl enable-linger pramana           # lets the user's services run after logout
```

Check that you can log in as `pramana` with your key from another terminal **before** you close
the root session or turn off password logins. Then, as `pramana`:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"     # or open a new shell; check with: uv --version
git clone https://github.com/master-of-none/pramana.git && cd pramana
./scripts/install_without_torch.sh       # about 200 MB; the full install is 5-6 GB of PyTorch/CUDA
```

`uv` fetches Python 3.12 itself. **From now on run the program as `.venv/bin/pramana`**, not
`uv run`: `uv run` first syncs the environment and would install PyTorch and CUDA again.

Copy the database up (from your computer), into a data folder of its own:

```sh
ssh pramana@YOUR_SERVER 'mkdir -p ~/pramana-data'
scp "$HOME/pramana-public/pramana.sqlite3" pramana@YOUR_SERVER:pramana-data/
```

On the server, check it:

```sh
cd ~/pramana && PRAMANA_HOME=~/pramana-data .venv/bin/pramana excerpt today
PRAMANA_HOME=~/pramana-data .venv/bin/pramana excerpt sources | head -20   # 62 documents
```

## 3. Run Pramana as a service

```sh
mkdir -p ~/.config/pramana ~/.config/systemd/user
printf 'PRAMANA_AGENT_TOKEN=%s\n' "$(.venv/bin/pramana agent token)" > ~/.config/pramana/agent.env
chmod 600 ~/.config/pramana/agent.env
cat > ~/.config/systemd/user/pramana-excerpts.service <<EOF
[Unit]
Description=Pramana excerpt server (agent routes only, localhost)

[Service]
Environment=PRAMANA_HOME=%h/pramana-data
EnvironmentFile=%h/.config/pramana/agent.env
ExecStart=%h/pramana/.venv/bin/pramana serve --agent-only
Restart=on-failure

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload && systemctl --user enable --now pramana-excerpts
```

Check it from the server:

```sh
set -a; . ~/.config/pramana/agent.env; set +a
curl -H "Authorization: Bearer $PRAMANA_AGENT_TOKEN" "http://127.0.0.1:8000/api/excerpts/today?format=text"
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/excerpts/today        # expect 401
journalctl --user -u pramana-excerpts -n 20 --no-pager                               # if not
```

Nothing listens on a public address: the server binds `127.0.0.1` only.

## 4. Decide how much to trust Hermes with a shell

Hermes runs commands for you. Its [security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security)
says the `local` terminal backend "runs commands directly on the host with no isolation", to be
avoided on a shared server, and recommends the `docker` or `ssh` backend, a dedicated non-root
user, an explicit user allowlist and approval prompts. Choose before you run it all day:

| Option | Isolation | Cost |
| --- | --- | --- |
| **A. Same server, `local` backend, unprivileged user, approvals on `manual`** | The `pramana` user's Unix permissions only (no `sudo`, not in the `docker` group) | Fine to **test**; not what I would leave running unattended on a server that hosts other things |
| **B. A separate small VPS for Hermes and Pramana** | Complete: nothing else lives there | The price of a small VPS; Pramana is tiny and public-domain, so it moves easily |
| **C. `docker` backend plus a Pramana bridge** | Hermes' shell is in a container | A container cannot reach Pramana on the host's `127.0.0.1`, so Hermes would need an MCP tool for Pramana instead of `curl` (Phase 5, not built) |

The steps below work for A and B. Do A to try everything; decide before you leave it running.

## 5. Install Hermes, a free model and the skill

As `kishan` (once), because the installer needs a system library and `pramana` has no `sudo`:

```sh
sudo apt install -y libatomic1
```

As `pramana`. Download the installer and read it before you run it, and skip the browser
and computer-use tools (the installer fetches Chromium by default):

```sh
curl -fsSLO https://hermes-agent.nousresearch.com/install.sh
less install.sh
bash install.sh --skip-browser --skip-computer-use
export PATH="$HOME/.local/bin:$PATH"
hermes doctor
```

Hermes installs into `~/.hermes/` and `~/.local/bin/hermes`, bringing its own Python.

**Nous Portal.** Run `hermes setup --portal` (or `hermes auth add nous`) as the `pramana` user. The
documentation's provider table lists it as a device-code flow, so you should see a verification
URL in the terminal: open it in a browser on your own computer and approve it while the terminal
waits. The login is stored under the Linux user that ran it (`~/.hermes/auth.json`), so run it
as `pramana`. `hermes portal info` shows which provider is active, and `hermes auth add nous`
repairs an expired login. The documentation says Hermes' own Hermes 4 models are not
recommended inside Hermes Agent for the tool-calling loop; choose another model from the
free catalog.

**Another free model.** Get an API key from the provider (an OpenRouter or Google AI Studio account),
then run `hermes model` from the shell (not inside a chat) and choose the provider and a free
model, or add a key with `hermes auth add openrouter --api-key <key>`. See
[the free model](#the-free-model) for what to expect.

**Safe settings while you test:**

```sh
chmod 600 ~/.hermes/.env
mkdir -p ~/hermes-work
hermes config set approvals.mode manual     # every command asks first
hermes config set terminal.cwd ~/hermes-work
hermes config show
```

**Give Hermes the Pramana address and token** (the token never goes in a chat; messaging
platforms never ask for secrets, so it lives in `~/.hermes/.env`):

```sh
printf 'PRAMANA_URL=http://127.0.0.1:8000\n' >> ~/.hermes/.env
grep '^PRAMANA_AGENT_TOKEN=' ~/.config/pramana/agent.env >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

**Save the skill** from [hermes-skill/SKILL.md](hermes-skill/SKILL.md) as
`~/.hermes/skills/pramana-excerpt/SKILL.md` (copy it with `scp`, or paste it into that file).
Change `tz=Asia/Kolkata` and `seed=kishan` in it to yours. Then check and try it:

```sh
hermes chat --toolsets skills -q "What skills do you have?"
hermes chat
# then, inside the chat:  /pramana-excerpt send me today's excerpt
```

With approvals on `manual` it will show you the `curl` command and wait for your yes. **Try this
in the terminal before you connect any chat app**: a small free model that cannot follow a skill
is the likeliest thing to go wrong. Tell it a preference ("I prefer short verses") and check it
was saved: `cat ~/.hermes/memories/USER.md`. Hermes can claim to save without doing so.

### The free model

| Provider | Reported free allowance | Watch for |
| --- | --- | --- |
| Nous Portal (Hermes' own service) | Third-party pages describe a $0 tier with the free-model catalog, standard rate limits and no bundled credits; pay-as-you-go top-ups from about $1. Hermes' own docs describe only the subscription | Confirm the current tier and which models are free at portal.nousresearch.com; its docs do not say what is logged. Its login is a device-code flow: no SSH tunnel |
| Google Gemini API | Flash-class models; sources say 250 to 1,500 requests a day | Free-tier content may be used to improve Google's products |
| OpenRouter, models ending `:free` | 20 requests a minute, 50 a day (1,000 after buying $10 of credit) | Peak-hour slowness; free models can disappear |
| Groq | Per-model limits, around 1,000 a day for a 70B model | 6K to 12K tokens a minute may be too small for an agent's prompt |

These figures come from third-party pages that disagree; check each provider's own console (for
OpenRouter, `GET /api/v1/key` shows the limits on your key). A daily message plus some chat is a
handful of requests a day, but an agent turn that uses a tool can take two or three. If the model
returns `429` at 07:00, **that day's message is missed** unless you add a fallback model in
Hermes' provider settings. You accepted that the provider sees your chat; the excerpts are
public domain.

## 6. Connect Telegram

1. In Telegram, message **@BotFather**, send `/newbot`, choose a name and a username ending in
   `bot`, and keep the token it gives you secret.
2. Message **@userinfobot** to get your numeric user ID.
3. As `pramana`, run `hermes gateway setup`, choose Telegram, and enter the token and **only
   your user ID** (or put `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_ALLOWED_USERS=<your id>` in
   `~/.hermes/.env`). With no allowlist, Hermes denies everyone, which is what you want until
   it is set. Do not use any `ALLOW_ALL_USERS` setting.
4. `hermes gateway install` (a systemd user service), then `hermes gateway start` and
   `hermes gateway status`. Logs: `hermes logs gateway -f`. The `pramana` user already has
   linger enabled, so the service survives logout.
5. Message your bot: "send me today's excerpt".

## 7. Schedule the daily message

Hermes' scheduler runs inside the gateway (it checks every 60 seconds), so the gateway must be
running. Each scheduled run starts fresh, so the prompt must say everything. For example:

```sh
hermes cron create "daily at 7am" \
  "Use the pramana-excerpt skill. Fetch today's excerpt with tz=Asia/Kolkata and seed=kishan, then send it with its reference and attribution." \
  --skill pramana-excerpt --deliver telegram --timezone Asia/Kolkata
hermes cron list
hermes cron run <job>          # test it now; it fires on the next scheduler tick
```

The docs show this form but also say to check `hermes cron create --help` for the exact flags,
so do that if a flag is rejected. A scheduled run cannot ask you to approve a command: with the
default `cron_mode: deny`, a command that needs approval is refused, so run the test above and
read the result before you trust it. `telegram` delivers to the bot's home chat
(`TELEGRAM_HOME_CHANNEL`) or use `telegram:<chat id>`.

## 8. WhatsApp, when Telegram works

Hermes' WhatsApp support is a Baileys bridge over WhatsApp Web: you run `hermes whatsapp`, scan
a QR code (Settings → Linked Devices), set `WHATSAPP_ENABLED`, `WHATSAPP_MODE` and
`WHATSAPP_ALLOWED_USERS`, and the gateway starts the bridge. It is **unofficial**: use a spare
number, expect to re-pair after WhatsApp changes, and test scheduled delivery separately: the
cron documentation gives `whatsapp` as a target but no syntax for a specific WhatsApp chat. See
Hermes' own [WhatsApp page](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/whatsapp).

## What Hermes remembers and what Pramana does

| | Pramana | Hermes |
| --- | --- | --- |
| Texts, rights, offsets | yes | no |
| Your preferences, time zone, schedule | **no** | yes (a small profile, see below) |
| What it already sent you | **no** | not reliably: see below |
| Picking something about a theme | `topic` (needs the model and index, see below) | decides when to ask |

### Hermes' memory is small

Hermes keeps a user profile (`USER.md`, 1,375 characters) and its own notes (`MEMORY.md`, 2,200)
under `~/.hermes/memories/` (see [its memory documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)).
That holds settings ("short verses, no Aiyar texts, Asia/Kolkata"), **not a list of excerpt IDs**:
100 IDs of about 36 characters each would not fit. So the skill does not rely on a sent-list:

- **The daily message uses `today`** with your own `seed` and unchanged filters. It walks a fixed
  shuffle and **does not repeat for years**, with nothing to remember. Changing `kind` or
  `document` reshuffles it, so a repeat is possible after a change.
- **"Another one" uses `random`**, excluding the IDs already sent *in that conversation*.
- Scheduled runs start fresh, so the schedule's prompt carries the settings (`tz`, `seed`, any
  filters) itself rather than assuming memory.

### Topic search on the server

This install leaves out PyTorch, so it cannot embed a question: `topic` works with
**`strategy=lexical`** (keywords, using the index you built), and the default `hybrid` returns a
`409` that says so. Tell Hermes to add `strategy=lexical` to topic searches (the skill below
does). Lexical search is cruder than hybrid: it matches words, not meaning, so "fear" finds
passages that use the word. Hermes can try a few related words. If you want hybrid, install the
full environment (`uv sync --locked`, 5-6 GB, about 1 GB of memory for the model), run
`pramana model setup`, and use `uv run`/`.venv/bin/pramana` as usual.

## Troubleshooting

| You see | Look at |
| --- | --- |
| Hermes does not answer on Telegram | `hermes gateway status`; `hermes logs gateway -f`; the user allowlist (`TELEGRAM_ALLOWED_USERS`); `hermes doctor` |
| Hermes answers but sends a verse "from memory" | The skill is not in `~/.hermes/skills/pramana-excerpt/SKILL.md`, or `PRAMANA_URL`/`PRAMANA_AGENT_TOKEN` are not in `~/.hermes/.env`; `hermes chat --toolsets skills -q "What skills do you have?"` |
| The scheduled job did nothing | The gateway is not running (`hermes cron status`, `hermes cron doctor`); a command was refused because scheduled runs cannot ask for approval; try `hermes cron run <job>` and read the result |
| Pramana `401` or `404` | Token missing or wrong in Hermes' environment; the service is not running |
| The daily message did not arrive | The model returned `429`/an error that morning; check Hermes' log; add a fallback model |
| Pramana `409` with `topic` | Add `strategy=lexical` (this install has no embedding library), or the index is missing |
| `pramana` reinstalls PyTorch | You ran `uv run`; use `.venv/bin/pramana` |

## Safety

- The Telegram or WhatsApp **allowlist** matters most: it decides who can talk to a program with
  access to your server.
- Give Pramana's token to Hermes only. Keep both under a non-root user, and expose no port.
- Your messages and the excerpts go to the free model provider; the excerpts are public domain,
  and Pramana's API cannot return your private books.
- Excerpt text is a quotation. The skill tells Hermes not to follow instructions found in it.
- Hermes' own advice for a shared server: a dedicated non-root user (done), an explicit user
  allowlist (above), `approvals.mode` at `smart` or `manual` and never `off` or `--yolo`, the
  `docker` or `ssh` terminal backend rather than `local`, `chmod 600 ~/.hermes/.env`, and
  `security.allow_private_urls` left `false`. `hermes update` and `hermes doctor` keep it
  current. See its [security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security).
- Never add the `pramana` user to `sudo` or the `docker` group (the latter is effectively root).

## What has and has not been tried

Verified here: building the public-only database (ingest and index, 591 chapters, 62 documents,
20 MB), the torch-free install from `scripts/install_without_torch.sh` (214 MB, the whole test
suite passes in it), the server run from `.venv/bin/pramana` on that database, lexical topic
search and the hybrid refusal, the systemd unit's syntax (`systemd-analyze verify`), and the
audit command. On the real server, the Pramana half has now been run by the owner (user,
install, database, service, and its checks). **Not tried:** installing Hermes, any free provider
with it, the skill file, Telegram, WhatsApp and Hermes cron. Those sections follow Hermes' official
documentation (installation, skills, Telegram, cron, memory, security and command reference
pages, read on 2 November 2026); exact flags such as `--deliver` are marked where the docs say to
check `--help`. `corpus download` and `model setup` were not re-run for this guide.
