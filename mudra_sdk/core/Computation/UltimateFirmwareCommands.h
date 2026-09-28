//
//  UltimateFirmwareCommands.h
//  Indriya — CONFIG (0xFFF1) command templates for Mudra ULTIMATE
//
//  Wire format: [cmd_id, feature, params...]
//  Trailing 0x00 bytes are placeholders filled by the SDK before send.
//
//  Independent of ProFirmwareCommands.h — verified against
//  mudra_ultimate/src/bt_layer/bt_command_manager.h, which defines its own
//  byte values from scratch rather than patching Pro's. Some feature bytes
//  coincide with Pro's (H_IMU/F_IMU/PPG/BAT/LED/BT_CTRL/TAP/STORAGE), some
//  don't (SYSTEM_USER_ID_SET, EMG_STATUS), and Ultimate has commands Pro
//  lacks entirely (SYSTEM_TSYNC/LINKSTATS, EMG_TEST/CHMASK/RLD/ISOLATE) while
//  lacking Pro's packet-loss *_TEST_MODE commands.
//

#ifndef UltimateFirmwareCommands_h
#define UltimateFirmwareCommands_h

#ifdef _WINDOWS
#ifdef  MUDRAWINDOWSDESKTOP_EXPORTS
#define DLLEXPORT __declspec(dllexport)
#else
#define DLLEXPORT __declspec(dllimport)
#endif
#else
#define DLLEXPORT
#endif

#include <vector>
#include <cstdint>
#include <cstddef>

namespace Mudra::Computation::Ultimate
{

    /* Action bytes shared by paired get/set + power features. */
    constexpr uint8_t BT_ACTION_GET   = 0x00;
    constexpr uint8_t BT_ACTION_SET   = 0x01;
    constexpr uint8_t BT_ACTION_STOP  = 0x00;
    constexpr uint8_t BT_ACTION_START = 0x01;

    /* ---- 0x00 SYSTEM ---- */
    constexpr uint8_t BT_CMD_SYSTEM        = 0x00;
    constexpr uint8_t BT_SYS_PING          = 0x00;
    constexpr uint8_t BT_SYS_VERSION       = 0x01;
    constexpr uint8_t BT_SYS_SERIAL        = 0x02;
    constexpr uint8_t BT_SYS_RING          = 0x03;
    constexpr uint8_t BT_SYS_DEVICE_INFO   = 0x04;
    constexpr uint8_t BT_SYS_LICENSE_SET   = 0x05;
    constexpr uint8_t BT_SYS_LICENSE_CLEAR = 0x06;
    /* 0x07 reserved for SHIP — kept aligned with Pro's SYSTEM numbering so
     * one host tool can speak both products' overlapping ranges; not used. */
    constexpr uint8_t BT_SYS_TSYNC         = 0x08; /* -> [ts_cyc:8 LE]; host clock-sync anchor */
    constexpr uint8_t BT_SYS_LINKSTATS     = 0x09; /* -> 19-byte BLE link/drop stats */
    constexpr uint8_t BT_SYS_USER_ID_SET   = 0x0A;
    constexpr size_t  BT_SYS_USER_ID_LEN   = 16;

    /* ---- 0x10 EMG ---- */
    constexpr uint8_t BT_CMD_EMG     = 0x10;
    constexpr uint8_t BT_EMG_POWER   = 0x00;
    constexpr uint8_t BT_EMG_ODR     = 0x01;
    constexpr uint8_t BT_EMG_RES     = 0x02;
    constexpr uint8_t BT_EMG_RES_MAX = 0x03;
    /* Bench self-test surface (bring-up), mirroring the CDC EMG_TEST /
     * EMG_CHMASK / EMG_RLD / EMG_ISOLATE tokens. All apply live, mid-stream. */
    constexpr uint8_t BT_EMG_TEST    = 0x04; /* GET -> u8 | SET <u8 0..4> input mux (3=temp, 4=supply) */
    constexpr uint8_t BT_EMG_CHMASK  = 0x05; /* GET -> u8 | SET <u8> bit n = ch n powered */
    constexpr uint8_t BT_EMG_RLD     = 0x06; /* GET -> u8 | SET <u8 0|1> bias amp */
    constexpr uint8_t BT_EMG_ISOLATE = 0x07; /* no action byte: stop PPG/IMUs/TinyTap/LEDs/advertising */
    constexpr uint8_t BT_EMG_STATUS  = 0x08; /* STATE — shifted vs. Pro to make room for TEST/CHMASK/RLD/ISOLATE */

    /* ---- 0x20 H_IMU ---- */
    constexpr uint8_t BT_CMD_H_IMU     = 0x20;
    constexpr uint8_t BT_H_IMU_POWER   = 0x00;
    constexpr uint8_t BT_H_IMU_ODR     = 0x01;
    constexpr uint8_t BT_H_IMU_ACC     = 0x02;
    constexpr uint8_t BT_H_IMU_GYR     = 0x03;
    constexpr uint8_t BT_H_IMU_ACC_RES = 0x04;
    constexpr uint8_t BT_H_IMU_GYR_RES = 0x05;
    constexpr uint8_t BT_H_IMU_ACC_BW  = 0x06;
    constexpr uint8_t BT_H_IMU_GYR_BW  = 0x07;
    constexpr uint8_t BT_H_IMU_ACC_AVG = 0x08;
    constexpr uint8_t BT_H_IMU_GYR_AVG = 0x09;
    constexpr uint8_t BT_H_IMU_STATUS  = 0x0a;

    /* ---- 0x30 F_IMU (same feature numbers as H_IMU) ---- */
    constexpr uint8_t BT_CMD_F_IMU     = 0x30;
    constexpr uint8_t BT_F_IMU_POWER   = 0x00;
    constexpr uint8_t BT_F_IMU_ODR     = 0x01;
    constexpr uint8_t BT_F_IMU_ACC     = 0x02;
    constexpr uint8_t BT_F_IMU_GYR     = 0x03;
    constexpr uint8_t BT_F_IMU_ACC_RES = 0x04;
    constexpr uint8_t BT_F_IMU_GYR_RES = 0x05;
    constexpr uint8_t BT_F_IMU_ACC_BW  = 0x06;
    constexpr uint8_t BT_F_IMU_GYR_BW  = 0x07;
    constexpr uint8_t BT_F_IMU_ACC_AVG = 0x08;
    constexpr uint8_t BT_F_IMU_GYR_AVG = 0x09;
    constexpr uint8_t BT_F_IMU_STATUS  = 0x0a;

    /* ---- 0x40 PPG ---- */
    constexpr uint8_t BT_CMD_PPG     = 0x40;
    constexpr uint8_t BT_PPG_POWER   = 0x00;
    constexpr uint8_t BT_PPG_ODR     = 0x01;
    constexpr uint8_t BT_PPG_DEC     = 0x02;
    constexpr uint8_t BT_PPG_LED     = 0x03;
    constexpr uint8_t BT_PPG_TIA     = 0x04;
    constexpr uint8_t BT_PPG_PRPCT   = 0x05;
    constexpr uint8_t BT_PPG_CLEAR   = 0x06;
    constexpr uint8_t BT_PPG_SRC     = 0x07;
    constexpr uint8_t BT_PPG_STATUS  = 0x08;

    /* ---- 0x50 BAT ---- */
    constexpr uint8_t BT_CMD_BAT       = 0x50;
    constexpr uint8_t BT_BAT_STATUS    = 0x00;
    constexpr uint8_t BT_BAT_SOC       = 0x01;
    constexpr uint8_t BT_BAT_VOLTAGE   = 0x02;
    constexpr uint8_t BT_BAT_CHARGING  = 0x03;
    constexpr uint8_t BT_BAT_CONNECTED = 0x04;
    constexpr uint8_t BT_BAT_RESET     = 0x05;

    /* ---- 0x60 LED ---- */
    constexpr uint8_t BT_CMD_LED       = 0x60;
    constexpr uint8_t BT_LED_SET_STATE = 0x00;
    constexpr uint8_t BT_LED_CLR_STATE = 0x01;
    constexpr uint8_t BT_LED_RGB       = 0x02;
    constexpr uint8_t BT_LED_BLINK     = 0x03;
    constexpr uint8_t BT_LED_OFF       = 0x04;
    constexpr uint8_t BT_LED_GET       = 0x05;

    /* ---- 0x70 BT_CTRL ---- */
    constexpr uint8_t BT_CMD_BT_CTRL     = 0x70;
    constexpr uint8_t BT_CTRL_ADV_START  = 0x00;
    constexpr uint8_t BT_CTRL_ADV_STOP   = 0x01;
    constexpr uint8_t BT_CTRL_ADV_GET    = 0x02;
    constexpr uint8_t BT_CTRL_CONN_GET   = 0x03;
    constexpr uint8_t BT_CTRL_NAME_SET   = 0x04;
    constexpr uint8_t BT_CTRL_NAME_GET   = 0x05;
    constexpr uint8_t BT_CTRL_NAME_RESET = 0x06;
    constexpr uint8_t BT_CTRL_PHY_SET    = 0x07;

    /* ---- 0x80 TAP ---- */
    constexpr uint8_t BT_CMD_TAP   = 0x80;
    constexpr uint8_t BT_TAP_POWER = 0x00;

    /* ---- 0x90 STORAGE ---- */
    constexpr uint8_t BT_CMD_STORAGE           = 0x90;
    constexpr uint8_t BT_STORAGE_RECORD_SET    = 0x00;
    constexpr uint8_t BT_STORAGE_RECORD_STATE  = 0x01;
    constexpr uint8_t BT_STORAGE_RECORD_ERROR  = 0x02;
    constexpr uint8_t BT_STORAGE_NEXT_FILE_NUM = 0x03;

    /* Fixed part of a RECORD_SET request — [cmd, feature, 4 sensor flags,
     * is_test, file_num, duration_min(u16 LE), utc_ts(u32 LE)] — a variable
     * description may follow, up to BT_CMD_MAX_LEN (96) total. Note: on
     * Ultimate, is_test only has an effect for EMG (see bt_command_manager.h) —
     * same wire layout as Pro, different firmware-side semantics. */
    constexpr size_t BT_STORAGE_RECORD_SET_FIXED_LEN = 14;

    class UltimateFirmwareCommands
    {
    public:

        enum FirmwareCommand {
            /* System */
            SYSTEM_PING,
            SYSTEM_VERSION,
            SYSTEM_SERIAL,
            SYSTEM_RING,
            SYSTEM_DEVICE_INFO,
            SYSTEM_LICENSE_SET,
            SYSTEM_LICENSE_CLEAR,
            SYSTEM_TSYNC,        /* [BT_CMD_SYSTEM, BT_SYS_TSYNC] -> [ts_cyc:8 LE] */
            SYSTEM_LINKSTATS,    /* [BT_CMD_SYSTEM, BT_SYS_LINKSTATS] -> 19-byte stats */

            /* EMG — trailing 0x00 bytes are SDK-filled */
            ENABLE_EMG,          /* [BT_CMD_EMG, BT_EMG_POWER, 0x00] action STOP|START */
            EMG_ODR,             /* [BT_CMD_EMG, BT_EMG_ODR, 0x00, 0x00, 0x00] action + u16 LE */
            EMG_RES,             /* [BT_CMD_EMG, BT_EMG_RES, 0x00, 0x00] action + u8 */
            EMG_RES_MAX,         /* [BT_CMD_EMG, BT_EMG_RES_MAX] */
            EMG_TEST,            /* [BT_CMD_EMG, BT_EMG_TEST, 0x00, 0x00] action + u8 mux mode 0..4 */
            EMG_CHMASK,          /* [BT_CMD_EMG, BT_EMG_CHMASK, 0x00, 0x00] action + u8 mask */
            EMG_RLD,             /* [BT_CMD_EMG, BT_EMG_RLD, 0x00, 0x00] action + u8 (0|1) */
            EMG_ISOLATE,         /* [BT_CMD_EMG, BT_EMG_ISOLATE] standalone */
            EMG_STATUS,          /* [BT_CMD_EMG, BT_EMG_STATUS] */

            /* Hand IMU */
            ENABLE_H_IMU,        /* [BT_CMD_H_IMU, BT_H_IMU_POWER, 0x00] */
            H_IMU_ODR,           /* [BT_CMD_H_IMU, BT_H_IMU_ODR, 0x00, 0x00, 0x00] */
            H_IMU_ACC,           /* [BT_CMD_H_IMU, BT_H_IMU_ACC, 0x00, 0x00] */
            H_IMU_GYR,           /* [BT_CMD_H_IMU, BT_H_IMU_GYR, 0x00, 0x00, 0x00] */
            H_IMU_ACC_RES,       /* [BT_CMD_H_IMU, BT_H_IMU_ACC_RES] */
            H_IMU_GYR_RES,       /* [BT_CMD_H_IMU, BT_H_IMU_GYR_RES] */
            H_IMU_ACC_BW,        /* [BT_CMD_H_IMU, BT_H_IMU_ACC_BW, 0x00, 0x00] */
            H_IMU_GYR_BW,        /* [BT_CMD_H_IMU, BT_H_IMU_GYR_BW, 0x00, 0x00] */
            H_IMU_ACC_AVG,       /* [BT_CMD_H_IMU, BT_H_IMU_ACC_AVG, 0x00, 0x00] */
            H_IMU_GYR_AVG,       /* [BT_CMD_H_IMU, BT_H_IMU_GYR_AVG, 0x00, 0x00] */
            H_IMU_STATUS,        /* [BT_CMD_H_IMU, BT_H_IMU_STATUS] */

            /* Finger IMU */
            ENABLE_F_IMU,        /* [BT_CMD_F_IMU, BT_F_IMU_POWER, 0x00] */
            F_IMU_ODR,
            F_IMU_ACC,
            F_IMU_GYR,
            F_IMU_ACC_RES,
            F_IMU_GYR_RES,
            F_IMU_ACC_BW,
            F_IMU_GYR_BW,
            F_IMU_ACC_AVG,
            F_IMU_GYR_AVG,
            F_IMU_STATUS,        /* [BT_CMD_F_IMU, BT_F_IMU_STATUS] */

            /* PPG */
            ENABLE_PPG,          /* [BT_CMD_PPG, BT_PPG_POWER, 0x00] */
            PPG_ODR,             /* [BT_CMD_PPG, BT_PPG_ODR, 0x00, 0x00, 0x00] */
            PPG_DEC,             /* [BT_CMD_PPG, BT_PPG_DEC, 0x00, 0x00] */
            PPG_LED,             /* [BT_CMD_PPG, BT_PPG_LED, 0x00, 0x00, 0x00, 0x00] action+ch+drv1+drv2 */
            PPG_TIA,             /* [BT_CMD_PPG, BT_PPG_TIA, 0x00, 0x00, 0x00, 0x00] action+ch+rf+cf */
            PPG_PRPCT,           /* [BT_CMD_PPG, BT_PPG_PRPCT, 0x00, 0x00, 0x00] */
            PPG_CLEAR,           /* [BT_CMD_PPG, BT_PPG_CLEAR] */
            PPG_SRC,             /* [BT_CMD_PPG, BT_PPG_SRC, 0x00, 0x00, 0x00, 0x00] action+ch+led+pd */
            PPG_STATUS,          /* [BT_CMD_PPG, BT_PPG_STATUS] */

            /* Battery */
            BAT_STATUS,
            BAT_SOC,
            BAT_VOLTAGE,
            BAT_CHARGING,
            BAT_CONNECTED,
            BAT_RESET,

            /* LED */
            LED_SET_STATE,       /* [BT_CMD_LED, BT_LED_SET_STATE, 0x00] state_id */
            LED_CLR_STATE,       /* [BT_CMD_LED, BT_LED_CLR_STATE, 0x00] */
            LED_RGB,             /* [BT_CMD_LED, BT_LED_RGB, 0x00, 0x00, 0x00, 0x00] r,g,b,anim */
            LED_BLINK,           /* [BT_CMD_LED, BT_LED_BLINK, 0x00, 0x00, 0x00, 0x00] r,g,b,count */
            LED_OFF,
            LED_GET,

            /* BT control */
            BT_ADV_START,
            BT_ADV_STOP,
            BT_ADV_GET,
            BT_CONN_GET,
            BT_NAME_SET,         /* [BT_CMD_BT_CTRL, BT_CTRL_NAME_SET] name appended by SDK */
            BT_NAME_GET,
            BT_NAME_RESET,
            BT_PHY_SET,          /* [BT_CMD_BT_CTRL, BT_CTRL_PHY_SET, 0x00] mode */

            /* TinyTap */
            ENABLE_TAP,          /* [BT_CMD_TAP, BT_TAP_POWER, 0x00] */

            /* Storage */
            STORAGE_RECORD_SET,     /* [BT_CMD_STORAGE, BT_STORAGE_RECORD_SET, emg,ppg,h_imu,f_imu,is_test,
                                       file_num, duration_min(u16 LE), utc_ts(u32 LE), desc...] */
            STORAGE_RECORD_STATE,   /* [BT_CMD_STORAGE, BT_STORAGE_RECORD_STATE] */
            STORAGE_NEXT_FILE_NUM,  /* [BT_CMD_STORAGE, BT_STORAGE_NEXT_FILE_NUM] */

            /* Recording-encryption user_id. RAM-only on the device, no
             * action byte, no getter (mirrors LICENSE_SET). */
            SYSTEM_USER_ID_SET,  /* [BT_CMD_SYSTEM, BT_SYS_USER_ID_SET, <16 raw bytes>] */
        };

        DLLEXPORT UltimateFirmwareCommands();
        DLLEXPORT ~UltimateFirmwareCommands();

        std::vector<uint8_t> getCommandBytes(FirmwareCommand cmd) {
            switch (cmd) {
                /* System */
                case FirmwareCommand::SYSTEM_PING:          return { BT_CMD_SYSTEM, BT_SYS_PING };
                case FirmwareCommand::SYSTEM_VERSION:       return { BT_CMD_SYSTEM, BT_SYS_VERSION };
                case FirmwareCommand::SYSTEM_SERIAL:        return { BT_CMD_SYSTEM, BT_SYS_SERIAL };
                case FirmwareCommand::SYSTEM_RING:          return { BT_CMD_SYSTEM, BT_SYS_RING };
                case FirmwareCommand::SYSTEM_DEVICE_INFO:   return { BT_CMD_SYSTEM, BT_SYS_DEVICE_INFO };
                case FirmwareCommand::SYSTEM_LICENSE_SET:   return { BT_CMD_SYSTEM, BT_SYS_LICENSE_SET };
                case FirmwareCommand::SYSTEM_LICENSE_CLEAR: return { BT_CMD_SYSTEM, BT_SYS_LICENSE_CLEAR };
                case FirmwareCommand::SYSTEM_TSYNC:         return { BT_CMD_SYSTEM, BT_SYS_TSYNC };
                case FirmwareCommand::SYSTEM_LINKSTATS:     return { BT_CMD_SYSTEM, BT_SYS_LINKSTATS };

                /* EMG */
                case FirmwareCommand::ENABLE_EMG:  return { BT_CMD_EMG, BT_EMG_POWER, 0x00 };
                case FirmwareCommand::EMG_ODR:     return { BT_CMD_EMG, BT_EMG_ODR, 0x00, 0x00, 0x00 };
                case FirmwareCommand::EMG_RES:     return { BT_CMD_EMG, BT_EMG_RES, 0x00, 0x00 };
                case FirmwareCommand::EMG_RES_MAX: return { BT_CMD_EMG, BT_EMG_RES_MAX };
                case FirmwareCommand::EMG_TEST:    return { BT_CMD_EMG, BT_EMG_TEST, 0x00, 0x00 };
                case FirmwareCommand::EMG_CHMASK:  return { BT_CMD_EMG, BT_EMG_CHMASK, 0x00, 0x00 };
                case FirmwareCommand::EMG_RLD:     return { BT_CMD_EMG, BT_EMG_RLD, 0x00, 0x00 };
                case FirmwareCommand::EMG_ISOLATE: return { BT_CMD_EMG, BT_EMG_ISOLATE };
                case FirmwareCommand::EMG_STATUS:  return { BT_CMD_EMG, BT_EMG_STATUS };

                /* Hand IMU */
                case FirmwareCommand::ENABLE_H_IMU:  return { BT_CMD_H_IMU, BT_H_IMU_POWER, 0x00 };
                case FirmwareCommand::H_IMU_ODR:     return { BT_CMD_H_IMU, BT_H_IMU_ODR, 0x00, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_ACC:     return { BT_CMD_H_IMU, BT_H_IMU_ACC, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_GYR:     return { BT_CMD_H_IMU, BT_H_IMU_GYR, 0x00, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_ACC_RES: return { BT_CMD_H_IMU, BT_H_IMU_ACC_RES };
                case FirmwareCommand::H_IMU_GYR_RES: return { BT_CMD_H_IMU, BT_H_IMU_GYR_RES };
                case FirmwareCommand::H_IMU_ACC_BW:  return { BT_CMD_H_IMU, BT_H_IMU_ACC_BW, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_GYR_BW:  return { BT_CMD_H_IMU, BT_H_IMU_GYR_BW, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_ACC_AVG: return { BT_CMD_H_IMU, BT_H_IMU_ACC_AVG, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_GYR_AVG: return { BT_CMD_H_IMU, BT_H_IMU_GYR_AVG, 0x00, 0x00 };
                case FirmwareCommand::H_IMU_STATUS:  return { BT_CMD_H_IMU, BT_H_IMU_STATUS };

                /* Finger IMU */
                case FirmwareCommand::ENABLE_F_IMU:  return { BT_CMD_F_IMU, BT_F_IMU_POWER, 0x00 };
                case FirmwareCommand::F_IMU_ODR:     return { BT_CMD_F_IMU, BT_F_IMU_ODR, 0x00, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_ACC:     return { BT_CMD_F_IMU, BT_F_IMU_ACC, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_GYR:     return { BT_CMD_F_IMU, BT_F_IMU_GYR, 0x00, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_ACC_RES: return { BT_CMD_F_IMU, BT_F_IMU_ACC_RES };
                case FirmwareCommand::F_IMU_GYR_RES: return { BT_CMD_F_IMU, BT_F_IMU_GYR_RES };
                case FirmwareCommand::F_IMU_ACC_BW:  return { BT_CMD_F_IMU, BT_F_IMU_ACC_BW, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_GYR_BW:  return { BT_CMD_F_IMU, BT_F_IMU_GYR_BW, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_ACC_AVG: return { BT_CMD_F_IMU, BT_F_IMU_ACC_AVG, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_GYR_AVG: return { BT_CMD_F_IMU, BT_F_IMU_GYR_AVG, 0x00, 0x00 };
                case FirmwareCommand::F_IMU_STATUS:  return { BT_CMD_F_IMU, BT_F_IMU_STATUS };

                /* PPG */
                case FirmwareCommand::ENABLE_PPG: return { BT_CMD_PPG, BT_PPG_POWER, 0x00 };
                case FirmwareCommand::PPG_ODR:    return { BT_CMD_PPG, BT_PPG_ODR, 0x00, 0x00, 0x00 };
                case FirmwareCommand::PPG_DEC:    return { BT_CMD_PPG, BT_PPG_DEC, 0x00, 0x00 };
                case FirmwareCommand::PPG_LED:    return { BT_CMD_PPG, BT_PPG_LED, 0x00, 0x00, 0x00, 0x00 };
                case FirmwareCommand::PPG_TIA:    return { BT_CMD_PPG, BT_PPG_TIA, 0x00, 0x00, 0x00, 0x00 };
                case FirmwareCommand::PPG_PRPCT:  return { BT_CMD_PPG, BT_PPG_PRPCT, 0x00, 0x00, 0x00 };
                case FirmwareCommand::PPG_CLEAR:  return { BT_CMD_PPG, BT_PPG_CLEAR };
                case FirmwareCommand::PPG_SRC:    return { BT_CMD_PPG, BT_PPG_SRC, 0x00, 0x00, 0x00, 0x00 };
                case FirmwareCommand::PPG_STATUS: return { BT_CMD_PPG, BT_PPG_STATUS };

                /* Battery */
                case FirmwareCommand::BAT_STATUS:    return { BT_CMD_BAT, BT_BAT_STATUS };
                case FirmwareCommand::BAT_SOC:       return { BT_CMD_BAT, BT_BAT_SOC };
                case FirmwareCommand::BAT_VOLTAGE:   return { BT_CMD_BAT, BT_BAT_VOLTAGE };
                case FirmwareCommand::BAT_CHARGING:  return { BT_CMD_BAT, BT_BAT_CHARGING };
                case FirmwareCommand::BAT_CONNECTED: return { BT_CMD_BAT, BT_BAT_CONNECTED };
                case FirmwareCommand::BAT_RESET:     return { BT_CMD_BAT, BT_BAT_RESET };

                /* LED */
                case FirmwareCommand::LED_SET_STATE: return { BT_CMD_LED, BT_LED_SET_STATE, 0x00 };
                case FirmwareCommand::LED_CLR_STATE: return { BT_CMD_LED, BT_LED_CLR_STATE, 0x00 };
                case FirmwareCommand::LED_RGB:       return { BT_CMD_LED, BT_LED_RGB, 0x00, 0x00, 0x00, 0x00 };
                case FirmwareCommand::LED_BLINK:     return { BT_CMD_LED, BT_LED_BLINK, 0x00, 0x00, 0x00, 0x00 };
                case FirmwareCommand::LED_OFF:       return { BT_CMD_LED, BT_LED_OFF };
                case FirmwareCommand::LED_GET:       return { BT_CMD_LED, BT_LED_GET };

                /* BT control */
                case FirmwareCommand::BT_ADV_START:  return { BT_CMD_BT_CTRL, BT_CTRL_ADV_START };
                case FirmwareCommand::BT_ADV_STOP:   return { BT_CMD_BT_CTRL, BT_CTRL_ADV_STOP };
                case FirmwareCommand::BT_ADV_GET:    return { BT_CMD_BT_CTRL, BT_CTRL_ADV_GET };
                case FirmwareCommand::BT_CONN_GET:   return { BT_CMD_BT_CTRL, BT_CTRL_CONN_GET };
                case FirmwareCommand::BT_NAME_SET:   return { BT_CMD_BT_CTRL, BT_CTRL_NAME_SET };
                case FirmwareCommand::BT_NAME_GET:   return { BT_CMD_BT_CTRL, BT_CTRL_NAME_GET };
                case FirmwareCommand::BT_NAME_RESET: return { BT_CMD_BT_CTRL, BT_CTRL_NAME_RESET };
                case FirmwareCommand::BT_PHY_SET:    return { BT_CMD_BT_CTRL, BT_CTRL_PHY_SET, 0x00 };

                /* TinyTap */
                case FirmwareCommand::ENABLE_TAP: return { BT_CMD_TAP, BT_TAP_POWER, 0x00 };

                /* Storage */
                case FirmwareCommand::STORAGE_RECORD_SET:
                    /* emg,ppg,h_imu,f_imu,is_test,file_num, duration_min(u16 LE), utc_ts(u32 LE) */
                    return { BT_CMD_STORAGE, BT_STORAGE_RECORD_SET,
                              0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                              0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
                case FirmwareCommand::STORAGE_RECORD_STATE:
                    return { BT_CMD_STORAGE, BT_STORAGE_RECORD_STATE };
                case FirmwareCommand::STORAGE_NEXT_FILE_NUM:
                    return { BT_CMD_STORAGE, BT_STORAGE_NEXT_FILE_NUM };

                /* Recording-encryption user_id */
                case FirmwareCommand::SYSTEM_USER_ID_SET: {
                    std::vector<uint8_t> tmpl(2 + BT_SYS_USER_ID_LEN, 0x00);
                    tmpl[0] = BT_CMD_SYSTEM;
                    tmpl[1] = BT_SYS_USER_ID_SET;
                    return tmpl;
                }

                default:
                    return { 0x00 };
            }
        }
    };
}

#endif
