//
//  ProCdcCommands.h
//  Indriya — CDC (USB serial) CONFIG-port command tokens for PRO
//
//  Wire format: ASCII line, "<TOKEN>\r\n" for a bare action or GET query
//  (query tokens end in '?'), "<TOKEN> <args...>\r\n" for a SET. Unlike
//  BLE's binary [cmd_id, feature, params...] frames (ProFirmwareCommands.h),
//  CDC has no single feature-byte scheme — every token below is verified
//  directly against mudra_pro's src/device_layer/usb_cdc/cdc_commands.c,
//  not derived from the BLE side.
//
//  Reuses ProFirmwareCommands::FirmwareCommand so the same logical command
//  has one enum value regardless of which transport actually sends it — e.g.
//  FirmwareCommand::EMG_ODR is {BT_CMD_EMG, BT_EMG_ODR, ...} over BLE and
//  "EMG_ODR" / "EMG_ODR?" over CDC. A command with no CDC equivalent at all
//  (system PING, every STORAGE_* — there are no SD-recording tokens on the
//  CDC CONFIG port) returns an empty string.
//
//  ENABLE_* commands (EMG/H_IMU/F_IMU/PPG/TAP power) have no single base
//  token over CDC the way BLE's one-command-plus-action-byte does — they're
//  two entirely different words ("EMG_ON" / "EMG_OFF"), so `enable` picks
//  between them; it's ignored for every other command.
//
//  Several tokens do NOT match FirmwareCommand's BLE-oriented naming:
//  combined status queries answer "EMG?" (not "EMG_STATUS?"), packet-loss
//  test-mode tokens have no underscore before MODE ("EMG_TESTMODE", not
//  "EMG_TEST_MODE"), and a handful of battery/LED/BT tokens are shortened
//  ("BAT_V" not "BAT_VOLTAGE", "LED_STATE" not "LED_SET_STATE", "BT_ADV" not
//  "BT_ADV_GET", etc.) — each one below is called out where it differs.
//
//  Independent of UltimateCdcCommands.h — see that file for Ultimate's token
//  set (byte-identical for shared commands, but Ultimate lacks *_TEST_MODE
//  and adds TSYNC/EMG_TEST/EMG_CHMASK/EMG_RLD/EMG_ISOLATE).
//

#ifndef ProCdcCommands_h
#define ProCdcCommands_h

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

#include "ProFirmwareCommands.h"

namespace Mudra::Computation::Pro
{

    class ProCdcCommands
    {
    public:

        using FirmwareCommand = ProFirmwareCommands::FirmwareCommand;

        DLLEXPORT ProCdcCommands();
        DLLEXPORT ~ProCdcCommands();

        /* ASCII token for `cmd`. For everything except the 5 ENABLE_*
         * (power) commands, `enable` is ignored and this returns the base
         * token for a paired GET/SET, standalone-GET, multi-arg, or
         * bare-action command — the caller already knows which shape a
         * given command needs (same design as getCommandBytes's zero-filled
         * placeholders: this returns the template, not the filled line) and
         * appends "?" for a GET or " <args...>" for a SET/action itself.
         * Combined status queries return their own full query text directly
         * since they don't follow the generic "<token>?" pattern. For an
         * ENABLE_* command, `enable` picks between the two unrelated ON/OFF
         * words CDC uses in place of BLE's single action-byte command
         * ("EMG_ON" vs "EMG_OFF", etc). Empty string = no CDC equivalent. */
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

                /* EMG */
                case FirmwareCommand::ENABLE_EMG:    return enable ? "EMG_ON" : "EMG_OFF";
                case FirmwareCommand::EMG_ODR:       return "EMG_ODR";
                case FirmwareCommand::EMG_RES:       return "EMG_RES";
                case FirmwareCommand::EMG_RES_MAX:   return "EMG_RES_MAX";
                case FirmwareCommand::EMG_STATUS:    return "EMG?";           /* not "EMG_STATUS?" */
                case FirmwareCommand::EMG_TEST_MODE: return "EMG_TESTMODE";   /* not "EMG_TEST_MODE" */

                /* Hand IMU */
                case FirmwareCommand::ENABLE_H_IMU:    return enable ? "H_IMU_ON" : "H_IMU_OFF";
                case FirmwareCommand::H_IMU_ODR:       return "H_IMU_ODR";
                case FirmwareCommand::H_IMU_ACC:       return "H_IMU_ACC";
                case FirmwareCommand::H_IMU_GYR:       return "H_IMU_GYR";
                case FirmwareCommand::H_IMU_ACC_RES:   return "H_IMU_ACC_RES";
                case FirmwareCommand::H_IMU_GYR_RES:   return "H_IMU_GYR_RES";
                case FirmwareCommand::H_IMU_ACC_BW:    return "H_IMU_ACC_BW";
                case FirmwareCommand::H_IMU_GYR_BW:    return "H_IMU_GYR_BW";
                case FirmwareCommand::H_IMU_ACC_AVG:   return "H_IMU_ACC_AVG";
                case FirmwareCommand::H_IMU_GYR_AVG:   return "H_IMU_GYR_AVG";
                case FirmwareCommand::H_IMU_STATUS:    return "H_IMU?";           /* not "H_IMU_STATUS?" */
                case FirmwareCommand::H_IMU_TEST_MODE: return "H_IMU_TESTMODE";   /* not "H_IMU_TEST_MODE" */

                /* Finger IMU */
                case FirmwareCommand::ENABLE_F_IMU:    return enable ? "F_IMU_ON" : "F_IMU_OFF";
                case FirmwareCommand::F_IMU_ODR:       return "F_IMU_ODR";
                case FirmwareCommand::F_IMU_ACC:       return "F_IMU_ACC";
                case FirmwareCommand::F_IMU_GYR:       return "F_IMU_GYR";
                case FirmwareCommand::F_IMU_ACC_RES:   return "F_IMU_ACC_RES";
                case FirmwareCommand::F_IMU_GYR_RES:   return "F_IMU_GYR_RES";
                case FirmwareCommand::F_IMU_ACC_BW:    return "F_IMU_ACC_BW";
                case FirmwareCommand::F_IMU_GYR_BW:    return "F_IMU_GYR_BW";
                case FirmwareCommand::F_IMU_ACC_AVG:   return "F_IMU_ACC_AVG";
                case FirmwareCommand::F_IMU_GYR_AVG:   return "F_IMU_GYR_AVG";
                case FirmwareCommand::F_IMU_STATUS:    return "F_IMU?";           /* not "F_IMU_STATUS?" */
                case FirmwareCommand::F_IMU_TEST_MODE: return "F_IMU_TESTMODE";   /* not "F_IMU_TEST_MODE" */

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
                case FirmwareCommand::PPG_TEST_MODE: return "PPG_TESTMODE";    /* not "PPG_TEST_MODE" */

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
