#pragma once

#include <mutex>
#include "display_images.h"
#include "persistent_state.h"

namespace postoffice {

// One RAM handoff for the existing single active claim; never a job queue.
class DisplayImageJob {
 public:
  bool accept(const Job& job, PersistentState& state);
  bool ownsClaim(const String& jobId) const;

  template<class Handler>
  bool handleStationResult(PersistentState& state, Handler handle) {
    // Cover both the ownership check and the serial write: an image claim
    // cannot be published between the check and a station terminal result.
    std::lock_guard<std::mutex> lock(mutex_);
    const String active = state.activeJobId();
    if (!active.isEmpty() && active == job_.id) return false;
    return handle();
  }

  template<class Renderer>
  bool processPending(PersistentState& state, Renderer render) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!pending_) return false;
    pending_ = false;  // Consume once, including renderer/NVS failure. No automatic retry.
    if (!state.healthy() || state.activeJobId() != job_.id || state.pendingResult().present)
      return false;
    const auto* image = localdisplay::findImage(job_.imageId);
    if (!image || !render(*image)) return state.queueRefused(job_.id, "display_failed");
    return state.queueDone(job_.id, "local_display");
  }

 private:
  mutable std::mutex mutex_;
  Job job_{};
  bool pending_ = false;
};

}  // namespace postoffice
