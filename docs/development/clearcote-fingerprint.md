# Clearcote fingerprint support on Chromium 150

This fork ports the fingerprint-related patches from
[Clearcote Browser](https://github.com/clearcotelabs/clearcote-browser/tree/9ac88dbb2f60340ecf49731f63fe8e04040754bb)
(Chromium **149.0.7827.114**) onto Electron's **150.0.7871.250** checkout.
Exact upstream and local baseline commits, patch hashes, and the included/excluded
upstream patch list are recorded in `patches/clearcote/UPSTREAM.json`.
The upstream BSD licenses are preserved alongside it.

## Enable

Set the switches before `app.whenReady()`, and before creating sessions/windows:

```js
const { app, BrowserWindow } = require('electron');

app.commandLine.appendSwitch('fingerprint', 'profile-001');
app.commandLine.appendSwitch('fingerprint-platform', 'windows');
app.commandLine.appendSwitch('fingerprint-brand', 'Chrome');
app.commandLine.appendSwitch('timezone', 'Europe/Lisbon');
// Optional explicit metadata overrides:
app.commandLine.appendSwitch('fingerprint-hardware-concurrency', '8');
app.commandLine.appendSwitch('fingerprint-device-memory', '8');

app.whenReady().then(() => {
  const window = new BrowserWindow({ webPreferences: { sandbox: true } });
  window.loadURL('https://example.com');
});
```

The same options work on the executable command line. Always select the intended
platform explicitly (`windows`, `linux`, `macos`, or `android`). The upstream seed
profile defaults are primarily Windows desktop profiles; importing a captured
profile is preferable when matching a specific device. Selecting an OS does not
install that OS's fonts or provide its physical GPU. Android viewport preferences
are forwarded, but the application still needs a matching window size.

The identity is **process-wide**, not per `Session`, partition, tab, or window.
Run separate Electron instances with separate user-data directories for independent
identities. Flags are read/cached natively; changing them after first use is not
supported. Explicit application/session User-Agent overrides can contradict the
fingerprint metadata and should be avoided when using persona UA/Client Hints.

Available controls include persona import (`fingerprint-profile`, gzip+base64 JSON),
GPU identity, CPU/RAM, screen/DPR/touch, timezone, fonts, canvas readbacks, WebGL/WebGPU,
audio metadata, media devices/capabilities, storage, battery/network metadata,
speech and geolocation. `disable-fingerprint-noise` preserves natural pixel
readbacks; `disable-gpu-fingerprint` uses the real GPU metadata and limits.
`fingerprint-tls-profile=chrome-150` keeps the native Chromium 150 TLS behavior.
WebRTC address replacement requires the explicit `webrtc-ip` flag; it is inherited
upstream behavior, not an implementation of a proxy or a guarantee of working ICE
connectivity. Canvas bridge transport remains opt-in via `canvas-bridge-url` and
requires an external compatible server.

## Integration and port changes

- `patches/chromium/feat_clearcote_fingerprint_chromium_150.patch` contains the
  fingerprint component, required ungoogled base hooks, Blink/content/network
  surfaces, GN dependencies, and a native regression test.
- `patches/webrtc/feat_clearcote_fingerprint_webrtc.patch` contains the separate
  WebRTC repository changes. Both patches are appended to their existing `.patches`
  queues and use Electron's normal `patches/config.json` import process.
- `shell/browser/electron_browser_client.cc` forwards a fixed allowlist of options
  to child processes, routes default UA and Client Hints through the fingerprint
  implementation, and supplies mobile viewport preferences. Chrome-only embedder
  hooks were replaced by Electron integration.
- The default Chrome identity uses the compiled engine version instead of the
  upstream random pool of Chromium 149 releases. A brand/profile version override
  remains an explicit user choice.
- Chromium 150 WebGL buffer bookkeeping and the current audio graph lock are
  preserved. Client Hint updates happen before the new header cache comparison.
- Native fallbacks are restored when fingerprinting is off. Keyboard layout
  substitution retains the browser permission check and asynchronous service path.
- The imported code is adapted to Chromium's checked spans, Blink container rules,
  and destructor/shadow warnings without disabling compiler checks.

Chrome Actor/LLM integration, humanized-input/cursor UI, V8 `Runtime.enable`
suppression, Chrome headless changes, and Chrome Windows cross-build fixes are
outside this fingerprint port. The source licenses and behavior are inherited;
this port does not claim every upstream spoof is indistinguishable from hardware.

## Build and verify

From the Chromium `src` directory, with depot_tools and GN on PATH:

```sh
export PATH="$PWD/buildtools/mac:$PWD/third_party/depot_tools:$PATH"
gn gen out/Testing
# The existing build configuration may require your remote build credentials.
autoninja -C out/Testing electron
```

For local compilation with this checkout's Siso configuration:

```sh
third_party/siso/cipd/siso ninja -C out/Testing -offline electron
```

Native regression tests can be built independently of the Electron/Blink rebuild:

```sh
third_party/siso/cipd/siso ninja -C out/Testing -offline components/ungoogled:clearcote_core_tests
out/Testing/clearcote_core_tests
```

To verify the patch artifacts against their recorded baselines and applied files:

```sh
python3 electron/script/clearcote/verify-patches.py
```

After rebuilding the application, run the browser-level probe (uses only a local
HTTP server, an isolated temporary profile, a frame, and a Web Worker):

```sh
node electron/script/clearcote/smoke.cjs "$PWD/out/Testing/Electron.app/Contents/MacOS/Electron"
```

It checks the native opt-out UA, UA/header/worker agreement on Chromium 150,
explicit CPU/RAM/screen/timezone values, and stable canvas output across reads
and launches with the same seed, with a different output for a different seed.
Use an equivalent executable path on other operating systems.

## Validation performed for this port

On macOS arm64: GN generation and Electron header dependency checks passed;
all 66 affected production C++ translation units passed the actual build's
compiler flags in syntax/type-check mode (including warnings-as-errors and
Chromium/Blink plugins); the native test executable was compiled, linked and ran
successfully. Both exported patches were replayed against their pinned baselines
and compared byte-for-byte with the working tree.

The complete Electron application has **not** been rebuilt or runtime-validated.
The initial full build stopped because the Node config generator could not find
`gn` on PATH, with approximately 17,000 build steps remaining. The PATH setting
above fixes that environment issue; the native test subsequently built successfully.
The existing Electron binary predates these changes. Browser-level, full-link,
Windows/Linux, and component-build behavior still require verification on a
rebuilt application. JavaScript smoke probes have been syntax-checked.

A broader `gn check out/Testing "//third_party/blink/*"` also reports the
pre-existing `font_matcher_mac.mm` include of `electron/mas.h` through a private
`ui/base` dependency. That include and dependency were already present at the
recorded baseline; they were not changed by this port. The new fingerprint and
canvas-bridge targets pass their own header dependency checks.
