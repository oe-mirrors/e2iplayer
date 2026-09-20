# MyE2iV3 - browser extension for E2iPlayer (v1.18)

MyE2iV3 lets a real browser solve what the receiver cannot: Cloudflare challenges, other
browser checks (DDoS-Guard, Anubis, ...) and captchas (reCAPTCHA, hCaptcha, Turnstile). The
receiver shows an address and a QR code, you open it in a browser with this extension, solve the
check there, and the result travels back to the receiver by itself. The receiver side is
`IPTVPlayer/scripts/mye2iserver.py` (a small web server started for every job) and
`IPTVPlayer/components/recaptcha_mye2i_widget.py` (the window on the receiver); the entry point
for hosts is `getPageCFProtection()` in `libs/pCommon.py` and `processCaptcha()` in
`components/captcha_helper.py`.

This folder is the complete source of the extension. It is based on the original 1.17
(http://www.e2iplayer.gitlab.io/mye2iv3_1.17.zip, hosted by a third party and not part of this
repository) and is loaded unpacked: `chrome://extensions` -> Developer mode -> "Load unpacked"
-> select this folder (or the unpacked release, see "Installation"). User guide with pictures:
https://github.com/oe-mirrors/e2iplayer/wiki/Solve-Cloudflare-hCaptcha-reCAPTCHA-with-MyE2i

Everything is additive: an unmodified original 1.17 keeps working with the current
`mye2iserver.py` (it simply never uses the newer features). `MIN_EXTENSION_VERSION` in the
server stays at 1.17; older versions get a hint on the receiver screen and in the browser.

## What is new compared with the original 1.17

### Fixes

- **Cloudflare detection (`main_e2itcf()` in `contentscripts/rc2ContentscriptProxy.js`).** The
  check could report "done" before Cloudflare had put its markers (`#challenge-form`, `<link>`,
  `<script>`) into the DOM (race with fast "managed challenges"). It now waits for
  `document.readyState == "complete"` and watches in-place DOM changes with a `MutationObserver`.
- **`ParamsExt`.** It crashed when a redirect after a passed challenge dropped the URL fragment
  (`document.location.hash` empty). It now falls back to empty parameters; the callers already
  have working fallbacks (e.g. the domain from the page URL).
- **Result token.** The base64 result was sent unencoded in the query string, so a `+` in it
  became a space on the server and the result arrived damaged (cookie values with `~` are enough).
  It is now percent-encoded (the regression case is `cf-cookie-with-plus-in-token` in the
  browser tests; the original 1.17 fails it).
- **Server handles connections in parallel** (`ThreadedServer`). Chrome opens spare, empty
  "preconnect" connections; while one was open, everything behind it hung (result, debug lines).
  It showed up as sporadic failures only in Chrome (3 of 10 test runs, 20 of 20 clean after the fix).

### Browser checks in general: the `COOKIES` mode

The page is opened, the extension waits until no known check page is shown any more
(Cloudflare, DDoS-Guard, Sucuri, Imperva/Incapsula, Anubis, PerimeterX/HUMAN, DataDome, AWS
WAF, Vercel, ...) and the page has not changed for 2.5 s, then sends ALL cookies of the site
(HttpOnly too) plus the User-Agent back (after 10 minutes at the latest it sends what it has). Check
pages are small: a large page that merely mentions a keyword (a "protected by DDoS-Guard" footer)
does not count.

`libs/botprotection.py` recognises from the response headers and the start of the page which system
answered. `getPageCFProtection()` writes it to the debug log as `PROTECTION: ...` and picks the mode:
Cloudflare challenge -> `CF` (cookie `cf_clearance`), cookie checks and unknown interactive
captchas -> `COOKIES`, hard blocks (Cloudflare WAF "Sorry, you have been blocked", Sucuri/Imperva/
Akamai error pages) -> MyE2i is not started at all, because a browser check would not help. For a
403 the headers and the start of the page are kept in `data.meta` (the text is still
"Access Forbidden"). GeeTest, Arkose/FunCaptcha, Friendly Captcha, Yandex SmartCaptcha are only
named (`KIND_CAPTCHA`); whether the cookie mode helps there depends on the site setting a cookie
after solving. Only tested against local imitations of DDoS-Guard and Anubis, never against a real
site.

### More captcha types

The type is part of the solver address (`#e2it?k=<sitekey>&st=<type>[&a=<action>][&d=<cdata>]`),
i.e. the `captchaType` / `captchaAction` / `captchaData` arguments of `processCaptcha()` (only the
MyE2i path knows action and cdata):

| `st`           | `a`    | What happens |
|----------------|--------|--------------|
| (empty)        | -      | reCAPTCHA v2, checkbox (`api.js`) |
| (empty)        | action | reCAPTCHA **v3** (`api.js?render=<key>`, `grecaptcha.execute(key, {action})`) |
| `INVISIBLE`    | -      | reCAPTCHA v2 invisible, a button starts `grecaptcha.execute()` |
| `ENTERPRISE`   | -      | reCAPTCHA Enterprise, checkbox (`enterprise.js`; an Enterprise site key is refused by `api.js`) |
| `ENTERPRISE`   | action | reCAPTCHA Enterprise **score key** (`enterprise.js?render=<key>`, `grecaptcha.enterprise.execute`) |
| `h1`           | -      | hCaptcha, checkbox (loaded from `js.hcaptcha.com`) |
| `h1_invisible` | -      | hCaptcha **invisible**, a button starts `hcaptcha.execute()` |
| `cf_re`        | -      | Cloudflare Turnstile (`a=` action and `d=` cdata are passed on) |
| `CF`           | -      | Cloudflare challenge (cookie `cf_clearance`) |
| `COOKIES`      | -      | any browser check, all cookies come back |

- A widget error (Turnstile/hCaptcha/reCAPTCHA `error-callback`, a rejected `execute()`: wrong key,
  refused action, ...) is shown as red text "Captcha error: <code>" on the page AND in the debug
  log of the receiver. Example: Cloudflare's always-failing test key `2x00000000000000000000AB`
  gives `600010`.
- Tested in Chrome 153, Edge 153 and Firefox 156: v3 and Enterprise score with an invalid key
  (script URL is right, the error is shown), hCaptcha invisible with hCaptcha's test site key
  (the token arrives), Turnstile with Cloudflare's test keys. There is no test key for reCAPTCHA
  v3 / Enterprise score, so a real token was never produced. `hostfilman.py` uses `ENTERPRISE`
  for its login (untested, no account); no host uses v3, score keys or hCaptcha invisible.

### Debug snapshot (for developing hosts)

Instead of guessing from curl output what a page really delivers (JS-rendered content, data
loaded by AJAX), the real browser loads the page and sends the result into the receiver's debug log.

**How:** open the receiver's page (`e2it.html`, QR code / `http://<receiver>:9001`) and **leave it
open**. At the bottom is a small "debug" button; it folds out a URL field (pre-filled with the
page the receiver asked for, change it to e.g. a video page) and the button **"Debug snapshot"**.
That opens the URL in a new tab with the fragment `#e2itdbg_sep_c=...`. If Cloudflare shows a
challenge there, solve it in that tab - the snapshot starts automatically afterwards. When it is
done a pop-up appears on the receiver.

**What ends up in the log** (as `[MyE2i-DUMP <section>]` lines, at most ~500 KB per section; the
complete file is also written to `<TmpDir>/mye2i_debug/<time>_<section>.txt` on the receiver,
`TmpDir` being the plugin's temporary folder setting):

| Section     | Content |
|-------------|---------|
| `meta`      | URL, title, User-Agent, waiting time |
| `dom`       | the fully rendered HTML (`documentElement.outerHTML`) |
| `resources` | all loaded URLs including fetch/XHR (Performance API) |
| `netlog`    | every `fetch()`/`XMLHttpRequest`: method, URL, request body, status and the first 3000 characters of the answer - what you need to rebuild a site's API |
| `cookies`   | cookie names, domain, flags (values cut to 40 characters) |

The cookies belong to the site in the tester's browser - look at the log before passing it on.

**How it works:** `POST /debugdump?name=<section>` in `mye2iserver.py` (the other endpoints are GET,
too small for a whole document); `contentscripts/dbgProbe.js` (injected by `background.js` after
every finished load of the debug tab - a Cloudflare redirect loses the URL fragment) and
`contentscripts/dbgHook.js` (runs in the page's world and records fetch/XHR, also after a redirect
within the session). Tested in real Edge 153, Chrome 153 and Firefox 156 against a local test
page (JS-rendered DOM, fetch POST, XHR, cookies) - without a real Cloudflare challenge.

### Debugging and diagnostics

- Every `e2ilog(...)` line of the challenge tab is passed on to the local `e2it.html` tab, which
  sends it to `mye2iserver.py` (`/debug`); it lands in the receiver's normal debug log, so the
  browser DevTools are no longer needed.
- On load the extension reports its version to `/version`; if it is too old, a hint appears on the
  receiver screen (not only inconspicuously in the browser).
- The receiver page shows a status line ("Waiting for the result ... (0:42)" -> "Done - the result
  was sent to the box").

### Firefox

Same sources, second package. One manifest cannot serve Chrome and Firefox, so
`build_release.py --firefox` generates a Firefox manifest from `manifest.json` (event page instead of
service worker, add-on ID `mye2iv3@e2iplayer`, no `key`) and packs `mye2iv3-firefox-unsigned.xpi`.

Tested (Firefox 156 headless, Marionette, temporary add-on): the Cloudflare cookie path,
Turnstile success and error display, the debug snapshot (all five sections), the same runs as in
Edge with the same results. Not tested: a real Cloudflare challenge, Firefox for Android, a signed
package.

Differences and limits in Firefox:
- Firefox 128 or newer (`world: "MAIN"`).
- Firefox evaluates `include_globs` without the `#` part of the URL. The scripts triggered by the
  fragment (`rc2ContentscriptProxy.js`, `dbgHook.js`) are therefore not in the Firefox manifest;
  `background.js` injects them when navigating (`IS_FIREFOX`, `webNavigation.onCommitted`).
- The fetch/XHR recording of the debug snapshot starts a moment after the page begins - calls in the
  very first parse moment may be missing (later ones are complete).
- `document.open()` breaks the extension context in Firefox, so the DOM is cleared directly
  (`e2iWipeDocument()`).
- The User-Agent in the result is Firefox's (`rv:...`). `cf_clearance` only works with the
  User-Agent that solved the challenge (see "Session memory" below).

Installation for testing: `about:debugging` -> "This Firefox" -> "Load Temporary Add-on..." -> the
`.xpi` (or the `manifest.json` of the unpacked folder). It disappears when Firefox restarts.
Permanently: Firefox (release/beta) only installs add-ons signed by Mozilla. Possible:
`web-ext sign --channel=unlisted --source-dir <unpacked xpi> --api-key ... --api-secret ...` (free
AMO account, API keys at addons.mozilla.org/developers/addon/api/key/); the result is a signed
`.xpi` that can be uploaded to the release. Without a signature it only works in Developer Edition,
Nightly and ESR with `xpinstall.signatures.required = false`. An automatic update would also need
`update_url` in the manifest (not implemented).

### Languages

The extension carries **no translations of its own** (there is no `_locales` folder). All visible
texts - the solver page, the status lines on `e2it.html`, the code page, the error pages of the
server - are translated by the E2iPlayer plugin with its normal translation (the language of
E2iPlayer, not the browser's): `recaptcha_mye2i_widget.py` hands the translations to
`mye2iserver.py` at start (`CAPTCHA_DATA['i18n']`); the server puts them into its own pages and
passes those of the extension on (the page `e2it.html` as a JSON block, the solver page as the
parameter `l=` in the address fragment). A missing translation (language not translated yet, old
plugin) stays English: the English text is built into the server (`DEFAULT_TEXTS`) and is the
fallback in the extension.

A new text is an entry in `DEFAULT_TEXTS` (server), the same key as `_("...")` in `_serverTexts()`
of the widget and - only if the extension shows it - `e2iText('key', 'English')` there.
`mye2i-extension/tests/test_mye2i_texts.py` checks that the three places agree.

## Access to the local server (setting "MyE2i extension: increase security")

Settings -> Captcha configuration. Default **off**: the plain address `http://<receiver>:<port>`
opens the page directly, as with the original extension - no code, no key (the QR code carries the
plain address). Anyone in the local network who guesses address and port could then hand a result to
the receiver while a job is open. **On:** the receiver window title shows a six-digit **code**, and
`mye2iserver.py` only serves the page and accepts results, debug lines and dumps from devices that
have identified themselves:
- **QR code:** carries the address with a random key (`/?t=<key>`); scanning is enough, nothing to type;
- **address typed by hand:** the plain address shows a small page asking for the code from the window
  title. After 10 wrong entries (all devices together) the code is locked for this session, the QR
  code keeps working;
- a device that has identified itself is remembered (by IP): requests without the key are accepted
  from there. That is why extensions older than 1.18 (also the original 1.17) keep working: they open
  the page that way but do not repeat the key in their own `/response` and `/debug` requests;
- everything else (another device that knows neither QR code nor code) only gets the code page or 403.

The served page carries the key in a `<meta>` tag; the extension sends it with every request.
`/version` stays open. Weak point: trust is tied to the IP (it does not help behind a shared
NAT/proxy address). Without a key in the server configuration (test runs) everything is accepted.
The page is served from memory, nothing is written to the plugin folder.

## Plugin side (in this branch of the plugin, no extension needed)

- **Session memory.** A `cf_clearance` cookie only works with the User-Agent of the browser that solved the
  challenge. `getPageCFProtection()` remembers that User-Agent next to the cookie file
  (`<cookie file>.ua`) and uses it for every later request through the same cookie file (= the same
  site). Before, the next page (category, video) went out with another User-Agent, Cloudflare refused the
  cookie and the receiver asked for the captcha again at every click. How long the release lasts is up
  to the site (Cloudflare's default is 30 minutes, often longer); after that the receiver asks again.
  The file lives in the cookie folder, so it follows the storage settings and is removed by the
  cookie cache cleanup.
- **Help window.** The window with address and QR code has a help (YELLOW / INFO / HELP): a short
  guide and a QR code that leads to the wiki page.
- **QR codes** of up to 106 characters (`libs/web_qr.py` picks QR version 3, 4 or 5; the wiki address
  did not fit into the former fixed version 3).
- **Status line.** `mye2iserver.py` and `fakejd.py` report to the plugin with one JSON line on
  stderr. It used to be the printed form of a bytes object (`b'{...}'`), which the MyJDownloader
  widget could not parse on Python 3 at all and which damaged apostrophes and non-ASCII characters in
  the MyE2i widget.
- The crash report of the host and subtitle dialogs no longer sends anything (the old report server
  is gone); `pwget.py` and `reporthostcrash.py` moved to `Backup/`.

## Installation / updates

Download (always the current version, fixed link - the same one is `UPDATE_URL` in
`IPTVPlayer/scripts/mye2iserver.py` and is shown in the browser banner and on the receiver screen
when the installed extension is too old):

    https://github.com/oe-mirrors/e2iplayer/releases/download/mye2i-extension/mye2iv3-latest.zip

1. Unpack the `.zip` (folder `mye2iv3`).
2. `chrome://extensions` (Edge: `edge://extensions`) -> Developer mode -> "Load unpacked" -> select the
   folder `mye2iv3`.
3. To update later: download the new `.zip`, overwrite the folder, press "Reload" in
   `chrome://extensions`.

**Extension ID:** the manifest contains a `key`, so the unpacked extension has the same ID on every
computer (`cdommeolkoiklmmlnmcommlfbljbelac`). It is NOT the ID of the original extension - an
already installed original is not replaced and should be removed.

**`.crx`:** also part of the release (`mye2iv3-latest.crx`). It is signed with a throw-away key
created for every build, so every build has a different extension ID (and the `.crx` manifest has no
`key`). Chrome/Edge do not install it by click outside of policies / developer mode - meant for
policy-based installations. There is no automatic update through `update_url`.

## Releases (automatic)

`.github/workflows/mye2i_extension_release.yml` runs after every merge to `python3` that changes
something in `mye2i-extension/` (except `tests/`) and by hand (`workflow_dispatch`). It builds with
`build_release.py --firefox --crx` and publishes twice:

| Release | Tag | Files | Purpose |
|---|---|---|---|
| Version (stays) | `mye2i-extension-v<version>` | `mye2iv3-<version>.zip` / `.crx`, `mye2iv3-firefox-unsigned-<version>.xpi` | history, created once per version |
| Current (replaced) | `mye2i-extension` | `mye2iv3-latest.zip` / `.crx`, `mye2iv3-firefox-unsigned.xpi` | fixed download addresses (update hint in the plugin, README, wiki) |

Neither is marked "Latest" (that stays with the plugin release from `tag_release.yml`). A new
version means raising `version` in `manifest.json`; without it only the files of the "Current" release
are replaced. The release notes list the commits that touch `mye2i-extension/` since the last version tag.

Building by hand: `python mye2i-extension/build_release.py --firefox --crx --out <folder>` (needs only
`openssl`, no browser; the CRX3 packer is part of `build_release.py`, tested in `mye2i-extension/tests/test_crx_build.py`
and against a `.crx` built by Edge). With `--pem <file>` the `.crx` is signed with a fixed key instead
and gets the fixed ID from the `key` field of the manifest. Never put that private key into the
repository; it is only needed for such a `.crx` with a fixed ID (the ID of the unpacked extension
depends on the `key` field alone).

Not automated: signing the Firefox `.xpi` at Mozilla (needs AMO API keys as secrets).

## Tests

- `python mye2i-extension/tests/run_browser_tests.py [chrome] [edge] [firefox]` drives real browsers
  headless through all flows (see the head of the file): 14 browser cases (Cloudflare cookie, cookie
  mode against local DDoS-Guard and Anubis imitations, debug snapshot, Turnstile, reCAPTCHA v3 /
  Enterprise, hCaptcha invisible, translated texts, ...) plus checks of the server itself (access
  control, translations, replies). Cases marked `[net]` need internet access. Useful options:
  `--only a,b`, `--repeat N`, `-v`, `--entry pin` (open the page the way the typed address does),
  `--ext-dir <folder>` (test an older unpacked extension, e.g. the original 1.17 - backward
  compatibility).
- `pytest mye2i-extension/tests` (from the repository root) covers the protection detection and the
  remembered User-Agent, the QR encoder, the CRX packer, the status line of the helper scripts and
  that the texts of server, plugin and extension agree. These tests are deliberately kept here and
  are not run by the repository's CI (`pytest tests/` only sees `tests/`); run both suites after
  every change to the MyE2i code. The `[net]` cases and the real browsers of the browser test need a
  desktop machine. `zxing-cpp` and `pillow` (optional) let the QR test decode the codes with a real
  reader.

The original extension is referenced in `IPTVPlayer/components/captchascriptwidget.py` /
`recaptcha_mye2i_widget.py` (the "Please Open site: http://IP:PORT..." text) and in
`IPTVPlayer/scripts/mye2iserver.py` (`UPDATE_URL` for the version hint, now pointing to the release above).
