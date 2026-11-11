#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
constexpr int LOW=0, HIGH=1, OUTPUT=1, INPUT=0;
unsigned long clockUs=1000000;
int pins[32]={}, pwm[32]={};
unsigned long echoPulse=5800;
std::vector<int> buzzerWrites;
unsigned long millis(){return clockUs/1000;}
unsigned long micros(){return clockUs;}
void delay(unsigned long ms){clockUs+=1000*ms;}
void delayMicroseconds(unsigned int us){clockUs+=us;}
void pinMode(int,int){}
void digitalWrite(int p,int v){pins[p]=v;if(p==13)buzzerWrites.push_back(v);}
int digitalRead(int p){return pins[p];}
void analogWrite(int p,int v){pwm[p]=v;}
unsigned long pulseIn(int,int,unsigned long timeout){clockUs+=echoPulse?echoPulse:timeout;return echoPulse;}
#include "generated-sketch.hpp"
void clearState(){
 clockUs=1000000;echoPulse=5800;for(int& p:pins)p=HIGH;for(int& p:pwm)p=0;
 IrReceiver.queue.clear();isAvoiding=false;isDancing=false;isCheckRequested=false;
 Drive_Num=GO_STOP;lastDriveCmd=GO_STOP;lastDriveCmdMs=0;lastCheckMs=0;
 stop_Music();isWarningIssued=false;lastWarnMs=0;isToneLow=false;buzzerWrites.clear();
}
void input(int command){IrReceiver.send(command);loop();}
int cases=0;
#define TEST(name, ...) do{clearState();__VA_ARGS__;cases++;std::cout<<"PASS "<<name<<"\n";}while(0)
int main(){
 TEST("startup",setup();assert(Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0&&pins[13]==HIGH));
 TEST("four directions",for(auto pair: {std::pair<int,DriveState>{IR_ADVANCE,GO_ADVANCE},{IR_BACK,GO_BACK},{IR_LEFT,GO_LEFT},{IR_RIGHT,GO_RIGHT}}){clearState();input(pair.first);assert(Drive_Num==pair.second&&pwm[9]==100&&pwm[6]==100);});
 TEST("opposite boundary",set_Drive(GO_ADVANCE);delay(300);set_Drive(GO_BACK);assert(Drive_Num==GO_STOP));
 TEST("opposite after boundary",set_Drive(GO_ADVANCE);delay(301);set_Drive(GO_BACK);assert(Drive_Num==GO_BACK));
 TEST("all diagonal orders",for(auto a:{GO_ADVANCE,GO_BACK})for(auto b:{GO_LEFT,GO_RIGHT}){assert(get_DiagonalDrive(a,b)!=DEF);assert(get_DiagonalDrive(a,b)==get_DiagonalDrive(b,a));});
 TEST("diagonal outputs",set_Drive(GO_ADVANCE);delay(100);set_Drive(GO_LEFT);do_Drive_Tick();assert(Drive_Num==GO_FORWARD_LEFT&&pwm[9]==130&&pwm[6]==75));
 TEST("numeric conflict before boundary",handle_NumberButton(69);delay(299);handle_NumberButton(70);assert(pendingSongNum==0));
 TEST("numeric new request at boundary",handle_NumberButton(69);delay(300);handle_NumberButton(70);assert(pendingSongNum==2&&pendingSongMs==millis()));
 TEST("numeric request after delayed loop",handle_NumberButton(69);delay(400);handle_NumberButton(70);delay(300);do_Music_Tick();assert(isMusicPlaying&&currentNotePtr==SONG_2));
 TEST("duplicate number preserves deadline",handle_NumberButton(69);auto start=pendingSongMs;delay(100);handle_NumberButton(69);assert(pendingSongMs==start));
 TEST("music starts at 300ms",handle_NumberButton(69);delay(299);do_Music_Tick();assert(!isMusicPlaying);delay(1);do_Music_Tick();assert(isMusicPlaying));
 TEST("music preserves drive",input(IR_ADVANCE);handle_NumberButton(69);delay(300);do_Music_Tick();assert(Drive_Num==GO_ADVANCE&&pwm[9]==100));
 TEST("music allows direction",play_Music(1);input(IR_LEFT);assert(isMusicPlaying&&Drive_Num==GO_LEFT));
 TEST("music switches via new request",play_Music(1);handle_NumberButton(70);delay(300);do_Music_Tick();assert(currentNotePtr==SONG_2));
 TEST("OK cancels everything",play_Music(1);start_Avoid(GO_BACK);isDancing=true;pendingSongNum=2;input(IR_STOP);assert(!isAvoiding&&!isDancing&&!isMusicPlaying&&!isWarningPlaying&&pendingSongNum==0&&Drive_Num==GO_STOP&&pwm[9]==0&&pins[13]==HIGH));
 TEST("front obstacle overrides drive",echoPulse=580;input(IR_ADVANCE);assert(isAvoiding&&Drive_Num==GO_BACK));
 TEST("back obstacle overrides drive",pins[0]=LOW;input(IR_BACK);assert(isAvoiding&&Drive_Num==GO_ADVANCE));
 TEST("both obstacles rotate",echoPulse=580;pins[0]=LOW;input(IR_ADVANCE);assert(isAvoiding&&Drive_Num==GO_RIGHT));
 TEST("avoid 500ms",start_Avoid(GO_BACK);delay(500);update_Avoid();assert(!isAvoiding&&Drive_Num==GO_STOP&&pwm[9]==0));
 TEST("avoid detects blocked escape",start_Avoid(GO_BACK);pins[0]=LOW;update_Avoid();assert(!isAvoiding&&Drive_Num==GO_STOP));
 TEST("avoid preserves music",play_Music(1);start_Avoid(GO_BACK);assert(isMusicPlaying&&isWarningPlaying));
 TEST("avoid ignores drive",start_Avoid(GO_BACK);input(IR_LEFT);assert(Drive_Num==GO_BACK));
 TEST("passive warning waveform",warning();for(int i=0;i<80;i++){delayMicroseconds(250);do_Warning_Tick();}int lows=0;for(int v:buzzerWrites)lows+=(v==LOW);assert(lows>20));
 TEST("warning silent phase",warning();delay(60);do_Warning_Tick();assert(pins[13]==HIGH&&warningPhase==1));
 TEST("warning deadline after delayed update",warning();delay(240);do_Warning_Tick();assert(!isWarningPlaying&&pins[13]==HIGH));
 TEST("warning resumes same note",play_Music(1);delay(50);auto start=noteStartMs;auto ptr=currentNotePtr;warning();delay(200);do_Music_Tick();assert(!isWarningPlaying&&isMusicPlaying&&currentNotePtr==ptr&&noteStartMs==start+200));
 TEST("warning interval including time zero",clockUs=0;warning();delay(200);do_Warning_Tick();delay(1);warning();assert(!isWarningPlaying);delay(799);warning();assert(isWarningPlaying));
 TEST("dance first output blocked",echoPulse=580;input(IR_DANCE);assert(!isDancing&&Drive_Num==GO_STOP&&pwm[9]==0));
 TEST("dance step transitions",input(IR_DANCE);assert(isDancing&&Drive_Num==GO_LEFT);delay(900);do_Dance_Tick();assert(Drive_Num==GO_RIGHT));
 TEST("dance ignores direction",input(IR_DANCE);input(IR_ADVANCE);assert(isDancing&&Drive_Num==GO_LEFT));
 TEST("dance restarts",input(IR_DANCE);danceStep=3;input(IR_DANCE);assert(danceStep==0&&Drive_Num==GO_LEFT));
 TEST("dance obstacle stops",input(IR_DANCE);pins[2]=LOW;delay(100);do_Dance_Tick();assert(!isDancing&&pwm[9]==0));
 TEST("dance duration",unsigned total=0;for(int i=0;i<DANCE_STEPS;i++)total+=dance_Duration(i);assert(total==5750));
 TEST("dance completion",start_Dance();for(int i=0;i<DANCE_STEPS;i++){delay(dance_Duration(i));do_Dance_Tick();}assert(isDancing&&danceStep==0&&Drive_Num==GO_LEFT));
 TEST("unknown and repeat ignored",input(IR_ADVANCE);input(255);IrReceiver.send(IR_BACK,IRDATA_FLAGS_IS_REPEAT);loop();assert(Drive_Num==GO_ADVANCE));
 TEST("invalid state stops",Drive_Num=static_cast<DriveState>(99);do_Drive_Tick();assert(Drive_Num==GO_STOP&&pwm[9]==0));
 TEST("song finishes",play_Music(9);for(int i=0;i<20&&isMusicPlaying;i++){delay(1000);do_Music_Tick();}assert(!isMusicPlaying&&pins[13]==HIGH));
 TEST("timeout existing policy",echoPulse=0;assert(watch()==999));
 TEST("diagonal slow input all orders",for(auto a:{GO_ADVANCE,GO_BACK})for(auto b:{GO_LEFT,GO_RIGHT})for(bool reverse:{false,true}){clearState();set_Drive(reverse?b:a);delay(10000);set_Drive(reverse?a:b);assert(Drive_Num==get_DiagonalDrive(a,b));});
 TEST("diagonal works after old deadline",set_Drive(GO_ADVANCE);delay(901);set_Drive(GO_LEFT);assert(Drive_Num==GO_FORWARD_LEFT));
 TEST("all diagonal PWM outputs",for(auto state:{GO_FORWARD_LEFT,GO_FORWARD_RIGHT,GO_BACK_LEFT,GO_BACK_RIGHT}){Drive_Num=state;do_Drive_Tick();bool outerRight=state==GO_FORWARD_LEFT||state==GO_BACK_RIGHT;assert(pwm[9]==(outerRight?130:75)&&pwm[6]==(outerRight?75:130));assert(pins[12]==(state==GO_FORWARD_LEFT||state==GO_FORWARD_RIGHT?HIGH:LOW));});
 TEST("diagonal component returns to single and requests sensors",set_Drive(GO_ADVANCE);delay(100);set_Drive(GO_LEFT);isCheckRequested=false;delay(900);set_Drive(GO_ADVANCE);assert(Drive_Num==GO_ADVANCE&&isCheckRequested));
 TEST("diagonal opposite last input stops",set_Drive(GO_ADVANCE);delay(100);set_Drive(GO_LEFT);delay(300);set_Drive(GO_RIGHT);assert(Drive_Num==GO_STOP));
 TEST("diagonal component returns to single after long pause",set_Drive(GO_ADVANCE);delay(100);set_Drive(GO_LEFT);delay(901);set_Drive(GO_ADVANCE);assert(Drive_Num==GO_ADVANCE));
 TEST("dance PWM independent of normal speed",input(IR_DANCE);assert(pwm[9]==180&&pwm[6]==180);input(IR_STOP);input(IR_LEFT);assert(pwm[9]==100&&pwm[6]==100));
 TEST("dance only spins and stops over three cycles",start_Dance();for(int cycle=0;cycle<3;cycle++){for(int i=0;i<DANCE_STEPS;i++){assert(Drive_Num==GO_LEFT||Drive_Num==GO_RIGHT||Drive_Num==GO_STOP);delay(dance_Duration(i));do_Dance_Tick();}assert(isDancing&&danceStep==0);}input(IR_STOP);assert(!isDancing&&pwm[9]==0&&pwm[6]==0));
 TEST("dance preserves active music cancels reservation",play_Music(1);handle_NumberButton(70);start_Dance();assert(isMusicPlaying&&pendingSongNum==0));
 TEST("remote all eight slow input orders",for(auto a:{IR_ADVANCE,IR_BACK})for(auto b:{IR_LEFT,IR_RIGHT})for(bool reverse:{false,true}){clearState();input(reverse?b:a);delay(3000);input(reverse?a:b);DriveState expected=get_DiagonalDrive(a==IR_ADVANCE?GO_ADVANCE:GO_BACK,b==IR_LEFT?GO_LEFT:GO_RIGHT);assert(Drive_Num==expected);input(IR_STOP);assert(Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0);});
 TEST("remote repeat does not undo diagonal",input(IR_ADVANCE);delay(2000);input(IR_LEFT);IrReceiver.send(IR_LEFT,IRDATA_FLAGS_IS_REPEAT);loop();assert(Drive_Num==GO_FORWARD_LEFT));
 TEST("OK resets diagonal pairing",input(IR_ADVANCE);input(IR_STOP);delay(2000);input(IR_LEFT);assert(Drive_Num==GO_LEFT));
 std::cout<<cases<<" host simulation cases passed; hardware not tested.\n";
}
