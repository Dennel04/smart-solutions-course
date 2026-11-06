"""Actual C++ handoff, renderer and NVS with synthetic SDK/display; no hardware IO."""
from pathlib import Path
import shutil
import subprocess

import pytest

from test_normal_firmware_safety import ARDUINO, PREFERENCES, FW

M5 = r'''
#pragma once
#include <cstdint>
#include <cassert>
constexpr int TFT_BLACK=0, TFT_GREEN=1, TFT_WHITE=2;
struct Display {
  int w=128,h=128,writes=0,stage=0;
  int width(){return w;} int height(){return h;}
  void startWrite(){stage=1;}
  void waitDMA(){assert(stage==2);stage=3;}
  void endWrite(){assert(stage==3);stage=4;}
  void fillScreen(int){++writes;}
  void setTextColor(int,int){} void setTextSize(int){} void setCursor(int,int){}
  void println(const char*){}
};
struct Device {struct Display Display;} ;
inline Device M5;
class M5Canvas {
 public:
  inline static bool alloc=true;
  explicit M5Canvas(Display*){}
  void setColorDepth(int){}
  void* createSprite(int,int){return alloc?this:nullptr;}
  void fillRect(int,int,int,int,uint16_t){++pixels;}
  void pushSprite(int,int){assert(pixels==256);assert(M5.Display.stage==1);M5.Display.stage=2;}
  void deleteSprite(){assert(M5.Display.stage==4);}
  int pixels=0;
};
'''
PROGRAM = r'''
#include "display_image_job.h"
#include "display_image_renderer.h"
#include <M5Unified.h>
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <future>
#include <chrono>
using namespace postoffice;
Job job(){Job j;strcpy(j.id,"image-job");strcpy(j.type,"display_image");
  strcpy(j.imageId,"lab2_logo");j.expiresEpoch=2000;return j;}
int main(int argc,char** argv){
  std::string mode=argv[1];int n=argc>2?atoi(argv[2]):0;
  PersistentState s;assert(s.begin());DisplayImageJob d;auto j=job();int draws=0;
  auto draw=[&](const localdisplay::Image& image){++draws;
    assert(s.activeJobId()==j.id);assert(!s.pendingResult().present);
    assert(Preferences::data["activeId"]==j.id);
    assert(std::string(image.id)==j.imageId);return true;};
  if(mode=="claim-fail"){
    Preferences::faults(1);assert(!d.accept(j,s));assert(!s.healthy());
    d.processPending(s,draw);assert(draws==0);return 0;
  }
  if(mode=="reject"){
    strcpy(j.imageId,"../x");assert(!d.accept(j,s));
    j=job();j.hasDirectMotionData=true;assert(!d.accept(j,s));
    j=job();strcpy(j.type,"letter");assert(!d.accept(j,s));
    assert(s.canPoll());assert(Preferences::operations==0);return 0;
  }
  if(mode=="legacy"){
    assert(s.startClaim("station-job"));assert(s.queueDone("station-job"));
    assert(s.pendingResult().source=="local_station");
    PersistentState reboot;assert(reboot.begin());assert(reboot.pendingResult().source=="local_station");
    assert(!reboot.queueDone("station-job","local_display"));return 0;
  }
  if(mode=="corrupt-source"){
    Preferences::data={{"resultReady","true"},{"resultId",j.id},
      {"resultStatus","done"},{"resultSource","unknown"}};
    PersistentState reboot;assert(!reboot.begin());assert(!reboot.canPoll());return 0;
  }
  if(mode=="serial-race"){
    std::future<bool> serial;std::promise<void> entered;auto started=entered.get_future();
    int calls=0;
    Preferences::afterWrite=[&](const char* key){
      if(std::string(key)!="activeId")return;
      serial=std::async(std::launch::async,[&]{entered.set_value();
        return d.handleStationResult(s,[&]{++calls;return s.queueDone(j.id);});});
      started.wait();
      assert(serial.wait_for(std::chrono::milliseconds(50))==std::future_status::timeout);
    };
    assert(d.accept(j,s));Preferences::afterWrite=nullptr;
    assert(!serial.get());assert(calls==0);assert(!s.pendingResult().present);
    assert(d.processPending(s,draw));assert(s.pendingResult().source=="local_display");return 0;
  }
  assert(d.accept(j,s));assert(d.ownsClaim(j.id));assert(!d.ownsClaim("another-job"));
  assert(!d.accept(j,s));assert(!s.canPoll());
  assert(!d.handleStationResult(s,[]{assert(false);return true;}));
  if(mode=="ambiguous"){
    PersistentState reboot;assert(reboot.begin());DisplayImageJob fresh;
    assert(!fresh.processPending(reboot,draw));
    assert(reboot.pendingResult().status=="refused");
    assert(reboot.pendingResult().reason=="ambiguous_after_reboot");
    assert(!d.processPending(reboot,draw));assert(draws==0);return 0;
  }
  if(mode=="renderer-fail"){
    assert(d.processPending(s,[&](const localdisplay::Image&){++draws;return false;}));
    assert(s.pendingResult().status=="refused");assert(s.pendingResult().reason=="display_failed");
  }else if(mode=="write-fail" || mode=="cut-terminal"){
    Preferences::faults(mode=="write-fail"?n:0,mode=="cut-terminal"?n:0);
    if(mode=="write-fail"){
      assert(!d.processPending(s,draw));assert(!s.healthy());assert(!s.canPoll());
      assert(Preferences::data["resultReady"]!="true");
    }else{try{d.processPending(s,draw);assert(false);}catch(PowerLoss&) {}}
    Preferences::faults();PersistentState reboot;assert(reboot.begin());DisplayImageJob fresh;
    assert(!fresh.processPending(reboot,draw));
    auto pending=reboot.pendingResult();
    assert(pending.status==(mode=="cut-terminal"&&n==4?"done":"refused"));
    assert(pending.source==(pending.status=="done"?"local_display":""));
  }else{
    if(mode=="geometry" || mode=="allocation" || mode=="lcd"){
      if(mode=="geometry")M5.Display.w=135;
      if(mode=="allocation")M5Canvas::alloc=false;
      assert(d.processPending(s,localdisplay::render));
      assert(s.pendingResult().status==(mode=="lcd"?"done":"refused"));
      if(mode!="lcd"){assert(M5.Display.stage==0);return 0;}
      assert(M5.Display.stage==4);localdisplay::showStatus("WiFi","changed");
      assert(M5.Display.writes==0);return 0;
    }
    assert(d.processPending(s,draw));assert(draws==1);
    assert(s.pendingResult().status=="done");assert(s.pendingResult().source=="local_display");
    Preferences::faults();assert(s.queueDone(j.id,"local_display"));
    assert(!s.queueDone(j.id));assert(!s.queueRefused(j.id,"late_station_result"));
    assert(Preferences::operations==0);
    PersistentState reboot;assert(reboot.begin());DisplayImageJob fresh;
    for(int i=0;i<3;++i){assert(reboot.pendingResult().source=="local_display");
      assert(!fresh.processPending(reboot,draw));assert(!fresh.accept(j,reboot));}
    if(mode=="ack-fail" || mode=="cut-ack"){
      Preferences::faults(mode=="ack-fail"?n:0,mode=="cut-ack"?n:0);
      if(mode=="ack-fail")assert(!reboot.acknowledgeResult(j.id));
      else{try{reboot.acknowledgeResult(j.id);assert(false);}catch(PowerLoss&) {}}
      Preferences::faults();PersistentState again;assert(again.begin());
      if(mode=="ack-fail"&&n==1)assert(again.pendingResult().source=="local_display");
      else{assert(again.canPoll());assert(!again.pendingResult().present);}
    }else{
      assert(reboot.acknowledgeResult(j.id));assert(reboot.canPoll());
      assert(!Preferences::data.count("resultSource"));
      assert(!s.queueDone(j.id,"local_display"));
    }
  }
  assert(!d.processPending(s,draw));assert(draws<=1);
}
'''


@pytest.fixture(scope="module")
def image_firmware(tmp_path_factory):
    folder = tmp_path_factory.mktemp("image-firmware")
    for name, content in {"Arduino.h": ARDUINO, "Preferences.h": PREFERENCES,
                          "M5Unified.h": M5, "test.cpp": PROGRAM}.items():
        (folder / name).write_text(content)
    binary = folder / "image-firmware"
    subprocess.run([shutil.which("c++"), "-std=c++17", "-pthread", "-I", str(folder),
                    "-I", str(FW / "include"), str(folder / "test.cpp"),
                    *[str(FW / "src" / name) for name in ["persistent_state.cpp",
                      "display_image_job.cpp", "display_image_renderer.cpp", "core/display_images.cpp"]],
                    "-o", str(binary)], check=True, capture_output=True)
    return binary


@pytest.mark.parametrize("mode", ["success", "claim-fail", "reject", "legacy", "ambiguous",
                                  "corrupt-source", "renderer-fail", "geometry", "allocation", "lcd", "serial-race"])
def test_actual_handoff_renderer_and_nvs(image_firmware, mode):
    subprocess.run([str(image_firmware), mode], check=True, timeout=10)


@pytest.mark.parametrize("mode", ["write-fail", "cut-terminal"])
@pytest.mark.parametrize("operation", range(1, 5), ids=["id", "status", "source", "ready"])
def test_each_display_result_write_and_interruption(image_firmware, mode, operation):
    subprocess.run([str(image_firmware), mode, str(operation)], check=True, timeout=10)


@pytest.mark.parametrize("mode", ["ack-fail", "cut-ack"])
@pytest.mark.parametrize("operation", range(1, 8))
def test_each_display_ack_cleanup_and_interruption(image_firmware, mode, operation):
    subprocess.run([str(image_firmware), mode, str(operation)], check=True, timeout=10)


def test_local_job_routes_before_serial_and_retries_persisted_source():
    client = (FW / "src/post_office_client.cpp").read_text()
    local_branch = client.index('if (strcmp(job.type, "display_image") == 0)', client.index('void PostOfficeClient::pollOnce'))
    dispatch = client.index('bridge_->dispatchJob', local_branch)
    assert 'return;  // Local LCD jobs' in client[local_branch:dispatch]
    assert 'document["result"]["source"] = pending.source' in client
    main = (FW / "src/main.cpp").read_text()
    serial = main[main.index('void pollSerialStationBoundary()'):main.index('void setup()')]
    assert serial.index('displayImageJob.handleStationResult') < serial.index('stationBridge.handleResultLine')
    assert 'displayImageJob.processPending(persistentState, localdisplay::render)' in main[main.index('void loop()'):]
    assert 'StationBridge' not in (FW / 'src/display_image_job.cpp').read_text()


@pytest.fixture(scope="module")
def image_parser(tmp_path_factory):
    """Compile the actual parser body/helpers against the cached ArduinoJson header.

    Only the SDK String input is adapted to std::string; no parser reimplementation.
    """
    library = FW / ".pio/libdeps/atoms3r_normal/ArduinoJson/src"
    if not (library / "ArduinoJson.h").is_file():
        pytest.skip("Parser host check requires ArduinoJson cached by NORMAL build")
    source = (FW / "src/post_office_client.cpp").read_text()
    helpers = source[source.index("int64_t daysFromCivil"):source.index("}  // namespace")]
    parser = source[source.index("bool PostOfficeClient::parseJobResponse"):source.index("void PostOfficeClient::pollOnce")]
    parser = parser.replace("PostOfficeClient::parseJobResponse", "parseJobResponse").replace("const String& response", "const std::string& response").replace("String& refusalReason", "std::string& refusalReason")
    program = r'''
#include <ArduinoJson.h>
#include <cstring>
#include <string>
#include <ctime>
#include <cassert>
#include <cstdlib>
#include "post_office_model.h"
#include "display_images.h"
using namespace postoffice;
constexpr int64_t kClockPlausibleAfter=1700000000LL;
size_t strlcpy(char* dst,const char* src,size_t count){
  size_t len=strlen(src);if(count){size_t copy=len<count-1?len:count-1;
  memcpy(dst,src,copy);dst[copy]=0;}return len;
}
''' + helpers + parser + r'''
int main(int argc,char**argv){Job job;bool present=false;std::string reason;
  bool ok=parseJobResponse(argv[1],job,present,reason);
  assert(ok==(std::string(argv[2])=="true"));
  if(ok){assert(present);assert(validateJob(job,time(nullptr),true).ok());}
}
'''
    folder = tmp_path_factory.mktemp("image-parser")
    (folder / "test.cpp").write_text(program)
    binary = folder / "parser"
    subprocess.run([shutil.which("c++"), "-std=c++17", "-I", str(library), "-I", str(FW / "include"),
                    str(folder / "test.cpp"), str(FW / "src/core/post_office_model.cpp"),
                    str(FW / "src/core/display_images.cpp"), "-o", str(binary)], check=True, capture_output=True)
    return binary


@pytest.mark.parametrize("arg,valid", [
    ({"image_id": "lab2_logo"}, True), ({"image_id": "lab2_check"}, True),
    ({"image_id": "unknown"}, False), ({"image_id": "https://example.invalid/a"}, False),
    ({"image_id": "../lab2_logo"}, False), ({"image_id": "lab2_logo", "x": 1}, False),
    ({"image_id": "lab2_logo", "letter": "A"}, False), ({"image_id": 1}, False),
    ({"image_id": "lab2_logo\x00anything"}, False), ({"image_id": None}, False),
    ({}, False), (["lab2_logo"], False), ("lab2_logo", False),
])
def test_actual_json_image_argument_parser(image_parser, arg, valid):
    import json
    response = {"job": {"id": "test-image", "job": "display_image", "arg": arg,
                        "expires_at": "2030-01-01T12:01:00Z"}}
    subprocess.run([str(image_parser), json.dumps(response), str(valid).lower()], check=True)


@pytest.mark.parametrize("job_type,arg,extra,expires,valid", [
    ("letter", {"letter": "A"}, {}, "2030-01-01T12:01:00Z", True),
    ("pick_place", {"routine": "source_to_finished"}, {}, "2030-01-01T12:01:00Z", True),
    ("letter", {"letter": "1"}, {}, "2030-01-01T12:01:00Z", False),
    ("pick_place", {"routine": "other"}, {}, "2030-01-01T12:01:00Z", False),
    ("display_image", {"image_id": "lab2_logo"}, {"pump": "on"}, "2030-01-01T12:01:00Z", False),
    ("display_image", {"image_id": "lab2_logo"}, {}, "2000-01-01T12:01:00Z", False),
    ("display_image", {"image_id": "lab2_logo"}, {}, "not-a-time", False),
])
def test_parser_preserves_ttl_and_other_jobs(image_parser, job_type, arg, extra, expires, valid):
    import json
    response = {"job": {"id": "test-image", "job": job_type, "arg": arg,
                        "expires_at": expires, **extra}}
    subprocess.run([str(image_parser), json.dumps(response), str(valid).lower()], check=True)
