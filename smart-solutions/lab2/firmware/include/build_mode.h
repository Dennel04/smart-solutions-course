#pragma once

// An omitted flag must never silently enable the normal post-office client.
#ifndef BENCH_MODE
#define BENCH_MODE 1
#endif
#if BENCH_MODE != 0 && BENCH_MODE != 1
#error "BENCH_MODE must be 0 or 1"
#endif
