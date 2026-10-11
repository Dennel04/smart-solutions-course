#pragma once

// Production HTTPS must use certificate validation. Add the real droplet
// hostname's CA through the ignored post_office_ca_private.h after the host is
// known. The committed foundation intentionally contains no fake certificate
// and never calls setInsecure().
#if __has_include("post_office_ca_private.h")
#include "post_office_ca_private.h"
#else
static constexpr const char* POST_OFFICE_ROOT_CA = nullptr;
#endif
