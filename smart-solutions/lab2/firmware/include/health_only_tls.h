#pragma once
#include "health_only_runtime.h"

namespace healthonly {
// Cert is mbedtls_x509_crt in firmware. Tests inject ONLY certificate structures
// and verification outcomes, not a different date/path policy.
template <class Cert> struct ChainCheck {
  int64_t utc;
  Cert* root;
  uint32_t invalidFlag;
  uint32_t depths = 0;
  bool anchor = false;
};
template <class Time> Date certificateDate(const Time& d) {
  return {d.year, d.mon, d.day, d.hour, d.min, d.sec};
}
template <class Cert>
int checkCertificate(void* context, Cert* cert, int depth, uint32_t* flags) {
  auto& check = *static_cast<ChainCheck<Cert>*>(context);
  if (!cert || depth < 0 || depth >= 8 || !flags) return -1;
  check.depths |= 1U << depth;
  if (!validity(certificateDate(cert->valid_from), certificateDate(cert->valid_to), check.utc))
    *flags |= check.invalidFlag;  // NEVER clear existing SDK flags
  if (cert->raw.len == check.root->raw.len && cert->raw.p && check.root->raw.p &&
      std::memcmp(cert->raw.p, check.root->raw.p, cert->raw.len) == 0) check.anchor = true;
  return 0;
}
template <class Cert, class Verify>
bool checkedChain(Cert* peer, Cert* root, int64_t utc, uint32_t invalidFlag, Verify verify) {
  if (!peer || !root || !utcValid(utc) || !invalidFlag) return false;
  ChainCheck<Cert> context;
  context.utc = utc; context.root = root; context.invalidFlag = invalidFlag;
  uint32_t flags = 0;
  const int result = verify(peer, root, kHost, &flags, checkCertificate<Cert>, &context);
  // Require a complete contiguous path, leaf and the exact local trust anchor.
  return result == 0 && flags == 0 && context.anchor && (context.depths & 1U) &&
      context.depths >= 3 && (context.depths & (context.depths+1)) == 0;
}
}  // namespace healthonly
