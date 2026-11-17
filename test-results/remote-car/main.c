/* ADセンサーとプッシュスイッチを使用するC版。 */
#define USL_AD_THRESHOLD 500
#define UCL_MOVE_STOP 0
#define UCL_MOVE_STRAIGHT 1
#define UCL_MOVE_LEFT 2
#define UCL_MOVE_RIGHT 3
#define UCL_ON 1
#define UCL_SW_OFF 0
#define UCL_SW_ON 1

/* ボード側のドライバーまたはPCテストのスタブが実装する。 */
extern unsigned char getSW(void);
extern unsigned short ADread(unsigned char channel);

unsigned char ucg_ONOFF = 0;

struct RemoteCarResult {
    unsigned short left;
    unsigned short right;
    unsigned char movement;
};

struct RemoteCarResult remote_car_step(void)
{
    struct RemoteCarResult result = {0, 0, UCL_MOVE_STOP};

    while (getSW() == UCL_SW_OFF) {
        /* 押されるまで待つ。 */
    }
    while (getSW() == UCL_SW_ON) {
        /* 離されるまで待つ。 */
    }

    if (ucg_ONOFF == UCL_ON) {
        result.left = ADread(0);
        result.right = ADread(1);

        if (result.left >= USL_AD_THRESHOLD && result.right < USL_AD_THRESHOLD) {
            result.movement = UCL_MOVE_LEFT;
        } else if (result.left < USL_AD_THRESHOLD && result.right >= USL_AD_THRESHOLD) {
            result.movement = UCL_MOVE_RIGHT;
        } else {
            result.movement = UCL_MOVE_STRAIGHT;
        }
    }
    return result;
}

#ifndef REMOTE_CAR_UNIT_TEST
int main(void)
{
    (void)remote_car_step();
    return 0;
}
#endif
