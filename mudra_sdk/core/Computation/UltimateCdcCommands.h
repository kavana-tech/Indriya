//
//  UltimateCdcCommands.h
//  Mudra Pro SDK — CDC (USB serial) CONFIG-port command tokens for ULTIMATE
//
//  Wire format: ASCII line, "<TOKEN>\r\n" for a bare action or GET query
//  (query tokens end in '?'), "<TOKEN> <args...>\r\n" for a SET. Unlike
//  BLE's binary [cmd_id, feature, params...] frames
//  (UltimateFirmwareCommands.h), CDC has no single feature-byte scheme —
//  every token below is verified directly against mudra_ultimate's
//  src/device_layer/usb_cdc/cdc_commands.c, not derived from the BLE side.
//
//  Reuses UltimateFirmwareCommands::FirmwareCommand so the same logical
//  command has one enum value regardless of which transport actually sends
//  it. A command with no CDC equivalent at all (system PING, LINKSTATS,
//  every STORAGE_*) returns an empty string.
//
//  Independent of ProCdcCommands.h — this table is byte-identical to Pro's
//  for every command both products share (verified: mudra_ultimate's
//  cdc_commands.c dispatcher/token set matches mudra_pro's for shared
//  tokens), but Ultimate lacks Pro's *_TEST_MODE tokens entirely and adds
//  TSYNC/EMG_TEST/EMG_CHMASK/EMG_RLD/EMG_ISOLATE, which Pro lacks.
//

#ifndef UltimateCdcCommands_h
#define UltimateCdcCommands_h

#ifdef _WINDOWS
#ifdef  MUDRAWINDOWSDESKTOP_EXPORTS
#define DLLEXPORT __declspec(dllexport)
#else
#define DLLEXPORT __declspec(dllimport)
#endif
#else
#define DLLEXPORT
#endif

#include <string>

#include "UltimateFirmwareCommands.h"

namespace Mudra::Computation::Ultimate
{

    class UltimateCdcCommands
    {
    public:

        using FirmwareCommand = UltimateFirmwareCommands::FirmwareCommand;

        DLLEXPORT UltimateCdcCommands();
        DLLEXPORT ~UltimateCdcCommands();

        /* ASCII token for `cmd`. See ProCdcCommands::getCommandToken for the
         * general shape rules (enable-only-for-ENABLE_*, "?"/args appended
         * by the caller, empty = no CDC equivalent). */
        std::string getCommandToken(FirmwareCommand cmd, bool enable = true) {
            switch (cmd) {
                /* System */
                case FirmwareCommand::SYSTEM_PING:          return "";  /* no CDC PING token; use CDC? as a round-trip probe instead */
                case FirmwareCommand::SYSTEM_VERSION:       return "VERSION";
                case FirmwareCommand::SYSTEM_SERIAL:        return "SERIAL";
                case FirmwareCommand::SYSTEM_RING:          return "RING";
                case FirmwareCommand::SYSTEM_DEVICE_INFO:   return "DEVICE_INFO";
                case FirmwareCommand::SYSTEM_LICENSE_SET:   return "LICENSE";
                case FirmwareCommand::SYSTEM_LICENSE_CLEAR: return "LICENSE_CLEAR";
                case FirmwareCommand::SYSTEM_TSYNC:         return "TSYNC";     /* "TSYNC?" -> "TSYNC ts_cyc=<u64>" */
                case FirmwareCommand::SYSTEM_LINKSTATS:     return "";          /* BLE-only (0x09), no CDC token */

                /* EMG */
                case FirmwareCommand::ENABLE_EMG:  return enable ? "EMG_ON" : "EMG_OFF";
                case FirmwareCommand::EMG_ODR:     return "EMG_ODR";
                case FirmwareCommand::EMG_RES:     return "EMG_RES";
                case FirmwareCommand::EMG_RES_MAX: return "EMG_RES_MAX";
                case FirmwareCommand::EMG_TEST:    return "EMG_TEST";    /* paired: "EMG_TEST?" / "EMG_TEST <0-4>" */
                case FirmwareCommand::EMG_CHMASK:  return "EMG_CHMASK"; /* SET-only over CDC, no "?" getter registered */
                case FirmwareCommand::EMG_RLD:     return "EMG_RLD";   /* SET-only over CDC, no "?" getter registered */
                case FirmwareCommand::EMG_ISOLATE: return "EMG_ISOLATE"; /* bare action, no "?" variant */
                case FirmwareCommand::EMG_STATUS:  return "EMG?";           /* not "EMG_STATUS?" */

                /* Hand IMU */
                case FirmwareCommand::ENABLE_H_IMU:  return enable ? "H_IMU_ON" : "H_IMU_OFF";
                case FirmwareCommand::H_IMU_ODR:     return "H_IMU_ODR";
                case FirmwareCommand::H_IMU_ACC:     return "H_IMU_ACC";
                case FirmwareCommand::H_IMU_GYR:     return "H_IMU_GYR";
                case FirmwareCommand::H_IMU_ACC_RES: return "H_IMU_ACC_RES";
                case FirmwareCommand::H_IMU_GYR_RES: return "H_IMU_GYR_RES";
                case FirmwareCommand::H_IMU_ACC_BW:  return "H_IMU_ACC_BW";
                case FirmwareCommand::H_IMU_GYR_BW:  return "H_IMU_GYR_BW";
                case FirmwareCommand::H_IMU_ACC_AVG: return "H_IMU_ACC_AVG";
                case FirmwareCommand::H_IMU_GYR_AVG: return "H_IMU_GYR_AVG";
                case FirmwareCommand::H_IMU_STATUS:  return "H_IMU?";           /* not "H_IMU_STATUS?" */

                /* Finger IMU */
                case FirmwareCommand::ENABLE_F_IMU:  return enable ? "F_IMU_ON" : "F_IMU_OFF";
                case FirmwareCommand::F_IMU_ODR:     return "F_IMU_ODR";
                case FirmwareCommand::F_IMU_ACC:     return "F_IMU_ACC";
                case FirmwareCommand::F_IMU_GYR:     return "F_IMU_GYR";
                case FirmwareCommand::F_IMU_ACC_RES: return "F_IMU_ACC_RES";
                case FirmwareCommand::F_IMU_GYR_RES: return "F_IMU_GYR_RES";
                case FirmwareCommand::F_IMU_ACC_BW:  return "F_IMU_ACC_BW";
                case FirmwareCommand::F_IMU_GYR_BW:  return "F_IMU_GYR_BW";
                case FirmwareCommand::F_IMU_ACC_AVG: return "F_IMU_ACC_AVG";
                case FirmwareCommand::F_IMU_GYR_AVG: return "F_IMU_GYR_AVG";
                case FirmwareCommand::F_IMU_STATUS:  return "F_IMU?";           /* not "F_IMU_STATUS?" */

                /* PPG */
                case FirmwareCommand::ENABLE_PPG: return enable ? "PPG_ON" : "PPG_OFF";
                case FirmwareCommand::PPG_ODR:    return "PPG_ODR";
                case FirmwareCommand::PPG_DEC:    return "PPG_DEC";
                case FirmwareCommand::PPG_LED:    return "PPG_LED";      /* multi-arg: "PPG_LED <ch> <drv1> <drv2>" / "PPG_LED? <ch>" */
                case FirmwareCommand::PPG_TIA:    return "PPG_TIA";      /* multi-arg: "PPG_TIA <ch> <rf> <cf>" / "PPG_TIA? <ch>" */
                case FirmwareCommand::PPG_PRPCT:  return "PPG_PRPCT";
                case FirmwareCommand::PPG_CLEAR:  return "PPG_CLEAR";    /* bare action, no "?" variant */
                case FirmwareCommand::PPG_SRC:    return "PPG_SRC";      /* multi-arg: "PPG_SRC <ch> <led> <pd>" / "PPG_SRC? <ch>" */
                case FirmwareCommand::PPG_STATUS: return "PPG?";              /* not "PPG_STATUS?" */

                /* Battery — several shortened vs. the BLE-oriented name */
                case FirmwareCommand::BAT_STATUS:    return "BAT";        /* not "BAT_STATUS" */
                case FirmwareCommand::BAT_SOC:       return "BAT_SOC";
                case FirmwareCommand::BAT_VOLTAGE:   return "BAT_V";      /* not "BAT_VOLTAGE" */
                case FirmwareCommand::BAT_CHARGING:  return "BAT_CHG";    /* not "BAT_CHARGING" */
                case FirmwareCommand::BAT_CONNECTED: return "BAT_CONN";   /* not "BAT_CONNECTED" */
                case FirmwareCommand::BAT_RESET:     return "BAT_RESET";  /* bare action, no GET */

                /* LED — several shortened vs. the BLE-oriented name */
                case FirmwareCommand::LED_SET_STATE: return "LED_STATE";  /* not "LED_SET_STATE" */
                case FirmwareCommand::LED_CLR_STATE: return "LED_CLR";    /* not "LED_CLR_STATE" */
                case FirmwareCommand::LED_RGB:       return "LED_RGB";    /* bare action, no GET */
                case FirmwareCommand::LED_BLINK:     return "LED_BLINK";  /* bare action, no GET */
                case FirmwareCommand::LED_OFF:       return "LED_OFF";    /* bare action, no GET */
                case FirmwareCommand::LED_GET:       return "LED?";       /* not "LED_GET?" */

                /* BT control — several shortened vs. the BLE-oriented name.
                 * BT_NAME_SET/BT_NAME_GET are separate BLE opcodes but share
                 * one CDC token ("BT_NAME" set / "BT_NAME?" get). */
                case FirmwareCommand::BT_ADV_START:  return "BT_ADV_START"; /* bare action */
                case FirmwareCommand::BT_ADV_STOP:   return "BT_ADV_STOP";  /* bare action */
                case FirmwareCommand::BT_ADV_GET:    return "BT_ADV?";      /* not "BT_ADV_GET?" */
                case FirmwareCommand::BT_CONN_GET:   return "BT_CONN?";     /* not "BT_CONN_GET?" */
                case FirmwareCommand::BT_NAME_SET:   return "BT_NAME";      /* not "BT_NAME_SET" */
                case FirmwareCommand::BT_NAME_GET:   return "BT_NAME?";     /* not "BT_NAME_GET?" */
                case FirmwareCommand::BT_NAME_RESET: return "BT_NAME_RESET"; /* bare action */
                case FirmwareCommand::BT_PHY_SET:    return "BT_PHY";       /* not "BT_PHY_SET" */

                /* TinyTap */
                case FirmwareCommand::ENABLE_TAP: return enable ? "TAP_ON" : "TAP_OFF";

                /* Storage — no CDC tokens exist at all (verified against
                 * cdc_commands.c: no RECORD_SET / RECORD_STATE / NEXT_FILE_NUM
                 * on the CDC CONFIG port). */
                case FirmwareCommand::STORAGE_RECORD_SET:
                case FirmwareCommand::STORAGE_RECORD_STATE:
                case FirmwareCommand::STORAGE_NEXT_FILE_NUM:
                    return "";

                default:
                    return "";
            }
        }
    };
}

#endif
