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
 TEST("four directions",for(auto pair: {std::pair<int,DriveState>{IR_ADVANCE,GO_ADVANCE},{IR_BACK,GO_BACK},{IR_LEFT,GO_LEFT},{IR_RIGHT,GO_RIGHT}}){delay(301);input(pair.first);assert(Drive_Num==pair.second&&pwm[9]==200&&pwm[6]==200);});
 TEST("opposite boundary",set_Drive(GO_ADVANCE);delay(300);set_Drive(GO_BACK);assert(Drive_Num==GO_STOP));
 TEST("opposite after boundary",set_Drive(GO_ADVANCE);delay(301);set_Drive(GO_BACK);assert(Drive_Num==GO_BACK));
 TEST("all diagonal orders",for(auto a:{GO_ADVANCE,GO_BACK})for(auto b:{GO_LEFT,GO_RIGHT}){assert(get_DiagonalDrive(a,b)!=DEF);assert(get_DiagonalDrive(a,b)==get_DiagonalDrive(b,a));});
 TEST("diagonal outputs",set_Drive(GO_ADVANCE);delay(100);set_Drive(GO_LEFT);do_Drive_Tick();assert(Drive_Num==GO_FORWARD_LEFT&&pwm[9]==200&&pwm[6]==100));
 TEST("numeric conflict before boundary",handle_NumberButton(69);delay(299);handle_NumberButton(70);assert(pendingSongNum==0));
 TEST("numeric new request at boundary",handle_NumberButton(69);delay(300);handle_NumberButton(70);assert(pendingSongNum==2&&pendingSongMs==millis()));
 TEST("numeric request after delayed loop",handle_NumberButton(69);delay(400);handle_NumberButton(70);delay(300);do_Music_Tick();assert(isMusicPlaying&&currentNotePtr==SONG_2));
 TEST("duplicate number preserves deadline",handle_NumberButton(69);auto start=pendingSongMs;delay(100);handle_NumberButton(69);assert(pendingSongMs==start));
 TEST("music starts at 300ms",handle_NumberButton(69);delay(299);do_Music_Tick();assert(!isMusicPlaying);delay(1);do_Music_Tick();assert(isMusicPlaying));
 TEST("music preserves drive",input(IR_ADVANCE);handle_NumberButton(69);delay(300);do_Music_Tick();assert(Drive_Num==GO_ADVANCE&&pwm[9]==200));
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
 TEST("dance step transitions",input(IR_DANCE);assert(isDancing&&Drive_Num==GO_LEFT);delay(400);do_Dance_Tick();assert(Drive_Num==GO_RIGHT));
 TEST("dance ignores direction",input(IR_DANCE);input(IR_ADVANCE);assert(isDancing&&Drive_Num==GO_LEFT));
 TEST("dance restarts",input(IR_DANCE);danceStep=3;input(IR_DANCE);assert(danceStep==0&&Drive_Num==GO_LEFT));
 TEST("dance obstacle stops",input(IR_DANCE);pins[2]=LOW;delay(100);do_Dance_Tick();assert(!isDancing&&pwm[9]==0));
 TEST("dance duration",unsigned total=0;for(int i=0;i<DANCE_STEPS;i++)total+=dance_Duration(i);assert(total==3450));
 TEST("dance completion",start_Dance();for(int i=0;i<DANCE_STEPS;i++){delay(dance_Duration(i));do_Dance_Tick();}assert(!isDancing&&Drive_Num==GO_STOP));
 TEST("unknown and repeat ignored",input(IR_ADVANCE);input(255);IrReceiver.send(IR_BACK,IRDATA_FLAGS_IS_REPEAT);loop();assert(Drive_Num==GO_ADVANCE));
 TEST("invalid state stops",Drive_Num=static_cast<DriveState>(99);do_Drive_Tick();assert(Drive_Num==GO_STOP&&pwm[9]==0));
 TEST("song finishes",play_Music(9);for(int i=0;i<20&&isMusicPlaying;i++){delay(1000);do_Music_Tick();}assert(!isMusicPlaying&&pins[13]==HIGH));
 TEST("timeout existing policy",echoPulse=0;assert(watch()==999));
 std::cout<<cases<<" host simulation cases passed; hardware not tested.\n";
}
