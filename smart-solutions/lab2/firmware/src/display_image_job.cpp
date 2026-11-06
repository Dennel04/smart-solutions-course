#include "display_image_job.h"

#include <cstring>

namespace postoffice {

bool DisplayImageJob::accept(const Job& job, PersistentState& state) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (pending_ || std::strcmp(job.type, "display_image") != 0 || job.hasDirectMotionData ||
      !localdisplay::findImage(job.imageId) || std::strcmp(job_.id, job.id) == 0) return false;
  // Keep ownership locked through claim persistence and handoff publication.
  // The serial-result path can never observe an image claim without its owner.
  if (!state.startClaim(job.id)) return false;
  job_ = job;
  pending_ = true;
  return true;
}

bool DisplayImageJob::ownsClaim(const String& jobId) const {
  std::lock_guard<std::mutex> lock(mutex_);
  return !jobId.isEmpty() && jobId == job_.id;
}

}  // namespace postoffice
