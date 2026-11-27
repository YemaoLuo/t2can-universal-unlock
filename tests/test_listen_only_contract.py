from pathlib import Path


root = Path(__file__).resolve().parents[1]
state = (root / "t2can_core_state.h").read_text(encoding="utf-8")
core = (root / "can_core.h").read_text(encoding="utf-8")
runtime = (root / "can_runtime.h").read_text(encoding="utf-8")
logic = (root / "vehicle_logic.h").read_text(encoding="utf-8")
api = (root / "web_api.h").read_text(encoding="utf-8")
ino = next(root.glob("*.ino")).read_text(encoding="utf-8")


def function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[brace : pos + 1]
    raise AssertionError(f"unclosed function: {signature}")


assert "static volatile bool listenOnlyEnabled = false;" in state
assert "static inline bool listenOnlyTxHeld()" in state
assert "__atomic_load_n(&listenOnlyEnabled, __ATOMIC_ACQUIRE)" in state

hold = function_body(core, "static void setCanTxAdministrativeHold(bool hold)")
assert hold.count("listenOnlyTxHeld()") == 2
supervisor = runtime[runtime.index("static void canUsbModeService()") :]
assert "listenOnlyTxHeld()" in supervisor

locked_tx = function_body(
    logic, "static esp_err_t autopilotControlTransmitLocked("
)
assert locked_tx.count("canTxAdministrativeHold") == 2
vision_observe = function_body(logic, "static void visionControlObserveBody(")
assert "canTxAdministrativeHold" in vision_observe

apply = function_body(logic, "static bool listenOnlyControlApply(bool enabled)")
assert 'featureBoolPersist("listenOnly", enabled)' in apply
assert apply.index("featureBoolPersist(") < apply.index("listenOnlyEnabled = enabled;")
assert "canTxAdministrativeHold = canTxAdministrativeRequested ||" in apply
assert "listenOnlyTxHeld()" in apply
assert "xSemaphoreGive(canTxBarrierMutex)" in apply

load = function_body(logic, "static void featureCfgLoad()")
assert 'prefs.getBool("listenOnly", false)' in load
assert "listenOnlyEnabled = persistedListenOnly;" in load
assert "setCanTxAdministrativeHold(canTxAdministrativeRequested);" in load

json = function_body(api, "static String listenOnlyControlJson()")
for key in ("enabled", "supported", "active"):
    assert f'jw.boolean("{key}"' in json
assert 'jw.boolean("supported", true)' in json
assert "listenOnlyTxHeld() && canTxAdministrativeHold" in json

get_handler = function_body(api, "static void httpListenOnlyControlConfig()")
assert "listenOnlyControlJson()" in get_handler
post = function_body(api, "static void httpListenOnlyControlUpdate()")
assert 'server.args() != 1 || !httpBoolArg("enabled", enabled)' in post
assert "listenOnlyControlApply(enabled)" in post
assert "503" in post
assert 'server.on("/api/listen-only/config", HTTP_GET, httpListenOnlyControlConfig);' in api
assert 'server.on("/api/listen-only/config", HTTP_POST, httpListenOnlyControlUpdate);' in api

assert "static void featureCfgLoad();" in (root / "t2can_forward.h").read_text(encoding="utf-8")
assert ino.count("featureCfgLoad();") == 1
assert ino.index("featureCfgLoad();") < ino.index('T2CAN_SERIAL_PRINTLN("[CAN A] Initializing MCP2515...")')

english = (root / "dashboard_source.html").read_text(encoding="utf-8")
chinese = (root / "zh-CN/dashboard_source_zh-CN.html").read_text(encoding="utf-8")
for dashboard in (english, chinese):
    assert 'id="listenOnlyRow"' in dashboard
    assert 'id="listenOnlyBanner"' in dashboard
    assert "banner.hidden=s?.enabled!==true" in dashboard
    assert 'id="listenOnlyToggle" type="checkbox" disabled/' in dashboard
    assert "url:'/api/listen-only/config'" in dashboard
    assert "$('listenOnlyToggle').onchange=updateListenOnlyControl;" in dashboard
    assert "await fetchListenOnlyControl();" in dashboard
    assert "pollDue('listenOnlyRecovery',1500,fetchListenOnlyControl,now,false)" in dashboard
assert "Listen-Only Mode" in english
assert "只听模式" in chinese

for relative in (
    "dashboard_demo.html",
    "zh-CN/dashboard_demo.zh-CN.html",
    "docs/index.html",
    "docs/index-zh-cn.html",
):
    demo = (root / relative).read_text(encoding="utf-8")
    assert 'id="listenOnlyRow"' in demo, relative
    assert 'id="listenOnlyBanner"' in demo, relative
    assert "path==='/api/listen-only/config'" in demo, relative

mock = (root / "tools/v38_preview_mock.js").read_text(encoding="utf-8")
assert "u.pathname==='/api/listen-only/config'" in mock

print("global listen-only state, TX gate, persistence, API, and bilingual UI: PASS")
