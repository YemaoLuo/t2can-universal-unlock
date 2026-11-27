"""Exercise the listen-only NVS transaction and global TX-hold transition."""

from pathlib import Path
import os
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LOGIC = (ROOT / "vehicle_logic.h").read_text(encoding="utf-8")


def function(name: str) -> str:
    match = re.search(
        r"^static\s+[^;{}]*?\b" + name + r"\([^;{}]*?\)\s*\{",
        LOGIC,
        re.M,
    )
    assert match, name
    end = LOGIC.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (LOGIC[end] == "{") - (LOGIC[end] == "}")
        end += 1
    return LOGIC[match.start() : end] + "\n"


code = r'''
#include <cassert>
#include <string>

constexpr int pdTRUE=1,portMAX_DELAY=-1;
int canTxBarrierMutex=1,listenOnlyControlMux=0;
bool held=false,busy=false,persistOk=true;
unsigned takeCalls=0,giveCalls=0,persistCalls=0;
bool listenOnlyEnabled=false;
bool canTxAdministrativeHold=false;
bool canTxAdministrativeRequested=false;
bool maintenanceHeld=false,usbHeld=false;
std::string persistedKey;
bool persistedValue=false;
void portENTER_CRITICAL(int*){}
void portEXIT_CRITICAL(int*){}
int xSemaphoreTake(int,int){++takeCalls;if(busy)return 0;assert(!held);held=true;return 1;}
void xSemaphoreGive(int){assert(held);held=false;++giveCalls;}
bool canMaintenanceActive(){return maintenanceHeld;}
bool canUsbTxHeld(){return usbHeld;}
bool listenOnlyTxHeld(){return listenOnlyEnabled;}
bool featureBoolPersist(const char* key,bool value){
  assert(held);++persistCalls;persistedKey=key;persistedValue=value;return persistOk;
}
'''
code += function("listenOnlyControlApply")
code += r'''
void reset(){
  held=busy=false;persistOk=true;takeCalls=giveCalls=persistCalls=0;
  listenOnlyEnabled=false;canTxAdministrativeHold=false;
  canTxAdministrativeRequested=false;maintenanceHeld=false;usbHeld=false;
  persistedKey.clear();persistedValue=false;
}
int main(){
  reset();busy=true;assert(!listenOnlyControlApply(true));
  assert(!listenOnlyEnabled&&!canTxAdministrativeHold&&persistCalls==0&&takeCalls==1&&giveCalls==0);

  reset();persistOk=false;assert(!listenOnlyControlApply(true));
  assert(!listenOnlyEnabled&&!canTxAdministrativeHold&&persistCalls==1&&takeCalls==1&&giveCalls==1&&!held);
  assert(persistedKey=="listenOnly"&&persistedValue);

  reset();assert(listenOnlyControlApply(true));
  assert(listenOnlyEnabled&&canTxAdministrativeHold&&persistCalls==1&&takeCalls==1&&giveCalls==1&&!held);
  assert(persistedKey=="listenOnly"&&persistedValue);

  reset();assert(listenOnlyControlApply(true));assert(listenOnlyControlApply(false));
  assert(!listenOnlyEnabled&&!canTxAdministrativeHold&&persistCalls==2&&giveCalls==2&&!held);
  assert(!persistedValue);

  reset();canTxAdministrativeRequested=true;
  assert(listenOnlyControlApply(true));assert(listenOnlyControlApply(false));
  assert(canTxAdministrativeHold);

  reset();maintenanceHeld=true;
  assert(listenOnlyControlApply(true));assert(listenOnlyControlApply(false));
  assert(canTxAdministrativeHold);

  reset();usbHeld=true;
  assert(listenOnlyControlApply(true));assert(listenOnlyControlApply(false));
  assert(canTxAdministrativeHold);
}
'''

with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / "listen_only.cpp"
    executable = Path(directory) / "listen_only"
    source.write_text(code, encoding="utf-8")
    subprocess.run(
        [
            os.environ.get("CXX", "c++"),
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(source),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)

print("Standalone listen-only NVS and global TX-hold transaction PASS")
