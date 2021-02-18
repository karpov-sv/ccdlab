void min_application_handler(uint8_t min_id, uint8_t seq, uint8_t *min_payload, uint8_t len_payload, uint8_t port)
{
#ifdef MIN_DEBUG_PRINTING 
  printf_init(Serial3);
  printf("app fr handler: id %i, pl: %.*s\n",min_id, len_payload, min_payload);
#endif
  // lets simpify things and requite all comands to be exactly 10 characters long (and additional payload after that ...)
  if (strlen(min_payload) < 10) return;
  String bb = String(seq)+":"; // we need to send back the sequence number of the request frame in order to be able to sort out to whom to send the reply
  if (strncmp("get_ardsta",min_payload,10) == 0) {
    bb = bb+"status="+String(my_status.temp_01);
    bb = bb+";"+String(my_status.temp_02);
    bb = bb+";"+String(my_status.humd_01);
    bb = bb+";"+String(my_status.humd_02);
    bb = bb+";"+String(my_status.switch_01);
    bb = bb+";"+String(my_status.switch_02);
    bb = bb+";"+String(my_status.switch_03);
    bb = bb+";"+String(my_status.switch_04);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  }
  
  if (strncmp("get_temp01",min_payload,10) == 0) {
    bb = bb+"temp01="+String(my_status.temp_01);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  }
  if (strncmp("get_humd01",min_payload,10) == 0) {
    bb = bb+"humd01="+String(my_status.humd_01);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  }
  if (strncmp("get_temp02",min_payload,10) == 0) {
    bb = bb+"temp02="+String(my_status.temp_02);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  }
  if (strncmp("get_humd02",min_payload,10) == 0) {
    bb = bb+"humd02="+String(my_status.humd_02);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  }
  if (strncmp("set_sw01on",min_payload,10) == 0) {
    digitalWrite(22, HIGH);
    my_status.switch_01=true;
    return;
  }
  if (strncmp("set_sw01of",min_payload,10) == 0) {
    digitalWrite(22, LOW);
    my_status.switch_01=false;
    return;
  } 
  if (strncmp("get_sw01st",min_payload,10) == 0) {
    bb = bb+"sw01="+String(my_status.switch_01);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  } 
  if (strncmp("set_sw02on",min_payload,10) == 0) {
    digitalWrite(23, HIGH);
    my_status.switch_02=true;
    return;
  }
  if (strncmp("set_sw02of",min_payload,10) == 0) {
    digitalWrite(23, LOW);
    my_status.switch_02=false;
    return;
  } 
  if (strncmp("get_sw02st",min_payload,10) == 0) {
    bb = bb+"sw02="+String(my_status.switch_02);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  }   
  
  if (strncmp("set_sw03on",min_payload,10) == 0) {
    digitalWrite(24, HIGH);
    my_status.switch_03=true;
    return;
  }
  if (strncmp("set_sw03of",min_payload,10) == 0) {
    digitalWrite(24, LOW);
    my_status.switch_03=false;
    return;
  } 
  if (strncmp("get_sw03st",min_payload,10) == 0) {
    bb = bb+"sw03="+String(my_status.switch_03);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  } 
  if (strncmp("set_sw04on",min_payload,10) == 0) {
    digitalWrite(25, HIGH);
    my_status.switch_04=true;
    return;
  }
  if (strncmp("set_sw04of",min_payload,10) == 0) {
    digitalWrite(25, LOW);
    my_status.switch_04=false;
    return;
  } 
  if (strncmp("get_sw04st",min_payload,10) == 0) {
    bb = bb+"sw04="+String(my_status.switch_04);
    min_queue_frame(&min_ctx, 1, bb.c_str(), bb.length());
    return;
  } 
}
