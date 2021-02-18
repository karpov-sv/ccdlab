//#define DISABLE_TRANSPORT_ACK_RETRANSMIT
//#define MIN_DEBUG_PRINTING

#ifdef MIN_DEBUG_PRINTING
#include <LibPrintf.h>
void min_debug_print(const char *msg, ...){
    va_list args;
    va_start(args, msg);
    printf(msg,args);
}
void printhex(char *bbuf, int bbuf_len){
  printf("len %i:",bbuf_len);
  for (int i = 0; i < bbuf_len; i ++) printf(" 0x%02X", (uint8_t)bbuf[i]);
  printf("\n");
}
#endif

#include "GY21.h"
#include "min.c"

struct min_context min_ctx;
uint32_t last_sent;
uint16_t min_tx_space(uint8_t port){ uint16_t n = Serial.availableForWrite(); return n;}
void min_tx_byte(uint8_t port, uint8_t byte) {Serial.write(&byte, 1U);}
void min_tx_start(uint8_t port){};
void min_tx_finished(uint8_t port){};
uint32_t min_time_ms(void) {return millis();}

struct ard_status {
  float temp_01;
  float humd_01;
  float temp_02;
  float humd_02;
  bool switch_01;
  bool switch_02;
  bool switch_03;
  bool switch_04;
} my_status{-1000,-1000,-1000,-1000,false,false,false,false};

#include "Arduino_A_appLevel.h"

GY21 *GY21_S01;
GY21 *GY21_S02;

void setup() {
  Serial.begin(115200);
  Serial.println("ard_id A");
  Serial.flush();
#ifdef MIN_DEBUG_PRINTING  
  Serial3.begin(115200);
 #endif 
  min_init_context(&min_ctx, 0);
  last_sent = millis();
  //GY21_S01 = new GY21(SDA,SCL);
  GY21_S01 = new GY21(40,41);
  GY21_S01->begin();
  GY21_S02 = new GY21(42,43);
  GY21_S02->begin();
  
  pinMode(22, OUTPUT); // the transistor swich will be here
  digitalWrite(22, LOW);
  pinMode(23, OUTPUT); // the transistor swich will be here
  digitalWrite(23, LOW);
  pinMode(24, OUTPUT); // the 230V swich will be here
  digitalWrite(24, LOW);
  pinMode(25, OUTPUT); // the 230V swich will be here
  digitalWrite(25, LOW);
}

void loop() {
  if (Serial3.readString().indexOf("reset") > 0) min_transport_reset(&min_ctx,false);
  char buf[32];
  size_t buf_len;
#ifdef MIN_DEBUG_PRINTING  
  Serial3.print(".");
#endif  
  if(Serial.available() > 0) {
#ifdef MIN_DEBUG_PRINTING
    Serial3.println("|");
#endif    
    buf_len = Serial.readBytes(buf, 32U);
    if ((buf_len >= 10 ) && ( strncmp("get_ard_id",buf,10) == 0 )) {
      Serial.println("ard_id A");
#ifdef MIN_DEBUG_PRINTING
      Serial3.println("ard_id A");
#endif    
      min_transport_reset(&min_ctx, false);
      buf_len = 0;
    }
#ifdef MIN_DEBUG_PRINTING
    printhex((uint8_t *)buf,(uint8_t)buf_len);
#endif    
  }
  else {
    buf_len = 0;
  }
  min_poll(&min_ctx, (uint8_t *)buf, (uint8_t)buf_len); 
  my_status.temp_01 = GY21_S01->GY21_Temperature();
  my_status.humd_01 = GY21_S01->GY21_Humidity();
  //my_status.temp_02 = GY21_S02->GY21_Temperature();
  //my_status.humd_02 = GY21_S02->GY21_Humidity();
}
