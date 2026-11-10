#pragma once
#include <cstdint>
#include <deque>
constexpr uint8_t IRDATA_FLAGS_IS_REPEAT = 1;
constexpr bool DISABLE_LED_FEEDBACK = false;
struct FakeReceiver {
 struct Data { int command = 0; uint8_t flags = 0; } decodedIRData;
 std::deque<Data> queue;
 bool decode() { if(queue.empty()) return false; decodedIRData=queue.front();queue.pop_front();return true; }
 void resume() {}
 void begin(int, bool) {}
 void send(int command, uint8_t flags=0) { queue.push_back({command,flags}); }
};
inline FakeReceiver IrReceiver;
