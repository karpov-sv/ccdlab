#ifndef GY21_H
#define GY21_H

#include <SoftwareWire.h>

//Default I2C address for the GY-21
#define GY21_I2C_ADDR    0x40

//Read temperature register
#define GY21_READ_TEMP   0xF3

//Read humidity register
#define GY21_READ_HUM    0xF5

//Time before give up readind new reg values
#define GY21_TIMEOUT     100

class GY21
{
  public:
    GY21(uint8_t sdaPin, uint8_t sclPin, boolean pullups = true, boolean detectClockStretch = true) {
        myWire = new SoftwareWire(sdaPin, sclPin, pullups, detectClockStretch);
    }
    
    void begin(){
        myWire->begin();
    }

    float GY21_Temperature()
    {
      uint8_t i = 0;
      this->setRegister(GY21_READ_TEMP);
      while (3 != myWire->requestFrom(GY21_I2C_ADDR, 3)) // IF THIS GOES, THE CODE GOES DOWN WITH IT
      {
        delay(1);
        i++;
        if (i > GY21_TIMEOUT)
          return _last_temp;
      }
      _last_temp = (((myWire->read() << 8) | (myWire->read() & 0b11111100)) * 0.002681274f - 46.85f);
      return _last_temp;
    }

    float GY21_Humidity()
    {
      uint8_t i = 0;
      this->setRegister(GY21_READ_HUM);
      while (3 != myWire->requestFrom(GY21_I2C_ADDR, 3)) // IF THIS GOES, THE CODE GOES DOWN WITH IT
      {
        delay(1);
        i++;
        if (i > GY21_TIMEOUT)
          return _last_hum;
      }
      _last_hum = (((myWire->read() << 8) | (myWire->read() & 0b11111100)) * 0.001907349f - 6.f);
      return _last_hum;
    }

  private:

    void setRegister(uint8_t reg)
    {
      myWire->beginTransmission(GY21_I2C_ADDR);   // Initialize the Tx buffer
      myWire->write(reg);            // Put slave register address in Tx buffer
      uint8_t error = myWire->endTransmission(false);  // Send the Tx buffer, but send a restart to keep connection alive
      if (error != 0 && error != 7)
      {
        Serial.print("I2C ERROR CODE : ");
        Serial.println(error);
      }
    }
    
    SoftwareWire *myWire;
    float _last_temp;
    float _last_hum;
};
#endif
