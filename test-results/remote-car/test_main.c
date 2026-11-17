#include <assert.h>
#include <stdio.h>
#define REMOTE_CAR_UNIT_TEST
#include "main.c"

struct TestCase {
    int id;
    unsigned char enabled, switches[5];
    unsigned short adc[2];
    unsigned short left, right;
    unsigned char movement, switch_calls, adc_calls, channels[2];
};

static const struct TestCase cases[] = {
    {1, 0, {0, 0, 0, 1, 0}, {499, 500}, 0, 0, 0, 5, 0, {0, 0}},
    {2, 1, {0, 0, 0, 1, 0}, {0, 0}, 0, 0, 1, 5, 2, {0, 1}},
    {3, 1, {0, 0, 0, 1, 0}, {499, 0}, 499, 0, 1, 5, 2, {0, 1}},
    {4, 1, {0, 0, 0, 1, 0}, {500, 0}, 500, 0, 2, 5, 2, {0, 1}},
    {5, 1, {0, 0, 0, 1, 0}, {501, 0}, 501, 0, 2, 5, 2, {0, 1}},
    {6, 1, {0, 0, 0, 1, 0}, {65535, 0}, 65535, 0, 2, 5, 2, {0, 1}},
    {8, 1, {0, 0, 0, 1, 0}, {0, 499}, 0, 499, 1, 5, 2, {0, 1}},
    {9, 1, {0, 0, 0, 1, 0}, {0, 500}, 0, 500, 3, 5, 2, {0, 1}},
    {10, 1, {0, 0, 0, 1, 0}, {0, 501}, 0, 501, 3, 5, 2, {0, 1}},
    {11, 1, {0, 0, 0, 1, 0}, {0, 65535}, 0, 65535, 3, 5, 2, {0, 1}},
    {12, 1, {0, 0, 0, 1, 0}, {499, 499}, 499, 499, 1, 5, 2, {0, 1}},
    {13, 1, {0, 0, 0, 1, 0}, {500, 500}, 500, 500, 1, 5, 2, {0, 1}},
    {14, 1, {0, 0, 0, 1, 0}, {501, 501}, 501, 501, 1, 5, 2, {0, 1}}
};

static const struct TestCase *current;
static unsigned switch_calls, adc_calls;
static unsigned char channels[2];

unsigned char getSW(void)
{
    assert(switch_calls < 5);
    return current->switches[switch_calls++];
}

unsigned short ADread(unsigned char channel)
{
    assert(adc_calls < 2 && channel < 2);
    channels[adc_calls++] = channel;
    return current->adc[channel];
}

int main(void)
{
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        current = &cases[i];
        ucg_ONOFF = current->enabled;
        switch_calls = adc_calls = 0;
        channels[0] = channels[1] = 0;
        struct RemoteCarResult result = remote_car_step();
        assert(result.left == current->left && result.right == current->right);
        assert(result.movement == current->movement);
        assert(switch_calls == current->switch_calls && adc_calls == current->adc_calls);
        assert(channels[0] == current->channels[0] && channels[1] == current->channels[1]);
        printf("PASS %d\n", current->id);
    }
    return 0;
}
