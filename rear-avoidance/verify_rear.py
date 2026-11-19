from pathlib import Path
import re,subprocess,tempfile
root=Path(__file__).resolve().parents[1]; tmp=tempfile.TemporaryDirectory(prefix='robot-rear-'); out=Path(tmp.name)
s=(root/'rear-avoidance/rear_avoidance/rear_avoidance.ino').read_text()
sigs=re.findall(r'^((?:void|bool|int|uint8_t|unsigned int|DriveState) \w+\([^\n]*\))\s*\{',s,re.M)
pos=s.index('DriveState Drive_Num');generated=s[:pos]+'\n'.join(x+';' for x in sigs)+'\n'+s[pos:];(out/'generated-sketch.hpp').write_text(generated)
t=(root/'tests/robot_test.cpp').read_text().replace('OUTPUT=1, INPUT=0;','OUTPUT=1, INPUT=0, INPUT_PULLUP=2, A0=14;')
t=t.replace('int pins[32]={}, pwm[32]={};','int pins[32]={}, pwm[32]={}, modes[32]={}, reads[32]={};\nint nextLeft=-1,nextRight=-1;')
t=t.replace('void delay(unsigned long ms){clockUs+=1000*ms;}','void delay(unsigned long ms){clockUs+=1000*ms;if(nextLeft>=0){pins[A0]=nextLeft;nextLeft=-1;}if(nextRight>=0){pins[2]=nextRight;nextRight=-1;}}')
t=t.replace('void pinMode(int,int){}','void pinMode(int p,int m){modes[p]=m;}').replace('int digitalRead(int p){return pins[p];}','int digitalRead(int p){++reads[p];return pins[p];}')
t=t.replace(' clockUs=1000000;echoPulse=5800;',' nextLeft=-1;nextRight=-1;for(int& m:modes)m=-1;for(int& r:reads)r=0;\n clockUs=1000000;echoPulse=5800;')
t=t.replace('pins[0]','pins[BACK_IR_L_PIN]')
t=t.replace('TEST("both obstacles while reversing rotate without automatic reverse",echoPulse=580;pins[BACK_IR_L_PIN]=LOW;input(IR_BACK);assert(isAvoiding&&Drive_Num==GO_RIGHT));', 'TEST("both obstacles while reversing stop without rotation",echoPulse=580;pins[BACK_IR_L_PIN]=LOW;input(IR_BACK);assert(!isAvoiding&&Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0&&isWarningPlaying));')
start=t.index(' TEST("remote rotate deadline"');end=t.index('\n',start)
t=t[:start]+' TEST("both obstacles remain stopped without automatic rotation",pins[BACK_IR_L_PIN]=LOW;echoPulse=580;input(IR_BACK);for(int i=0;i<5;i++){delay(100);loop();assert(!isAvoiding&&Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0);});'+t[end:]
extra='''
 TEST("automatic right avoidance rejected",start_Avoid(GO_RIGHT);assert(!isAvoiding&&Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0));
 TEST("rear A0 and D2 pullup initialization",setup();assert(BACK_IR_L_PIN==A0&&BACK_IR_R_PIN==2);assert(modes[A0]==INPUT_PULLUP&&modes[2]==INPUT_PULLUP&&modes[0]==-1));
 TEST("both rear pins read even when left active",pins[A0]=LOW;assert(is_BackIrOn());assert(reads[A0]==1&&reads[2]==1));
 TEST("rear inactive has no confirmation wait",auto start=millis();assert(!is_BackBlocked());assert(millis()==start));
 TEST("left stable confirmation waits 20ms",pins[A0]=LOW;auto start=millis();assert(is_BackBlocked());assert(millis()-start==20));
 TEST("left transient rejected",pins[A0]=LOW;nextLeft=HIGH;assert(!is_BackBlocked()));
 TEST("right transient rejected",pins[2]=LOW;nextRight=HIGH;assert(!is_BackBlocked()));
 TEST("alternating left to right rejected",pins[A0]=LOW;nextLeft=HIGH;nextRight=LOW;assert(!is_BackBlocked()));
 TEST("alternating right to left rejected",pins[2]=LOW;nextRight=HIGH;nextLeft=LOW;assert(!is_BackBlocked()));
 TEST("overlapping stable left accepted",pins[A0]=LOW;nextRight=LOW;assert(is_BackBlocked()));
 TEST("right alone initiates forward escape",pins[2]=LOW;input(IR_BACK);assert(isAvoiding&&Drive_Num==GO_ADVANCE&&pwm[9]==SPEED&&pwm[6]==SPEED&&isWarningPlaying));
 TEST("D0 no longer used for left detection",pins[0]=LOW;input(IR_BACK);assert(!isAvoiding&&Drive_Num==GO_BACK));
 TEST("rear diagonal directions escape",for(auto direction:{GO_BACK_LEFT,GO_BACK_RIGHT}){clearState();pins[A0]=LOW;Drive_Num=direction;isCheckRequested=true;checkSensorsAndObstacles();assert(isAvoiding&&Drive_Num==GO_ADVANCE);} );
 TEST("rear escape ends and stays stopped",pins[A0]=LOW;input(IR_BACK);delay(500);loop();assert(!isAvoiding&&Drive_Num==GO_STOP);for(int i=0;i<10;i++)loop();assert(!isAvoiding&&Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0));
 TEST("OK stops rear-triggered escape",pins[2]=LOW;input(IR_BACK);input(IR_STOP);assert(!isAvoiding&&Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0&&!isWarningPlaying));
 TEST("rear sensor aborts dance before output",pins[A0]=LOW;input(IR_DANCE);assert(!isDancing&&!isMusicPlaying&&Drive_Num==GO_STOP&&pwm[9]==0&&pwm[6]==0));
'''
t=t.replace(' std::cout<<cases<<',extra+' std::cout<<cases<<');(out/'test.cpp').write_text(t)
args=['g++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(root/'tests/stubs'),'-I'+str(out),str(out/'test.cpp'),'-o',str(out/'test')]
subprocess.run(args,check=True)
r=subprocess.run([str(out/'test')],check=True,capture_output=True,text=True);(out/'test-results.txt').write_text(r.stdout);print(r.stdout)
# Both active-high settings use the actual full sketch in a second translation unit.
hi=generated.replace('#define BACK_IR_L_ACTIVE_LEVEL LOW','#define BACK_IR_L_ACTIVE_LEVEL HIGH').replace('#define BACK_IR_R_ACTIVE_LEVEL LOW','#define BACK_IR_R_ACTIVE_LEVEL HIGH');(out/'high-sketch.hpp').write_text(hi)
head=t[:t.index('void clearState()')].replace('"generated-sketch.hpp"','"high-sketch.hpp"')
main='''int main(){pins[A0]=LOW;pins[2]=LOW;assert(!is_BackBlocked());pins[A0]=HIGH;assert(is_BackBlocked());pins[A0]=LOW;pins[2]=HIGH;assert(is_BackBlocked());std::cout<<"3 active-high cases passed.\\n";}'''
(out/'high.cpp').write_text(head+main)
subprocess.run(args[:-3]+[str(out/'high.cpp'),'-o',str(out/'high-test')],check=True)
r=subprocess.run([str(out/'high-test')],capture_output=True,text=True,check=True);print(r.stdout);(out/'test-results.txt').write_text((out/'test-results.txt').read_text()+r.stdout)
