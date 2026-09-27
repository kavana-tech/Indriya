#pragma once

namespace Mudra
{
	namespace Computation
	{
		/*
		 * BLE/USB DATA section (same shape on both transports):
		 *   [id:1][len:2 LE][payload:len][ts:8 LE]
		 * len = payload bytes; sample count = len / sample_size.
		 * ts  = last sample's ts_cyc (not send time).
		 */
		constexpr unsigned char DATA_HEADER_EMG   = 0x10;
		constexpr unsigned char DATA_HEADER_IMU_H = 0x20;
		constexpr unsigned char DATA_HEADER_IMU_F = 0x30;
		constexpr unsigned char DATA_HEADER_PPG   = 0x40;

		constexpr unsigned int DATA_SECTION_HEADER_SIZE = 3; /* id(1) + len(2) */
		constexpr unsigned int TIMESTAMP_SIZE = 8;
		constexpr unsigned int DATA_SECTION_OVERHEAD = DATA_SECTION_HEADER_SIZE + TIMESTAMP_SIZE;

		/* EMG payload: interleaved channels (3 on Pro, 8 on Ultimate), 16-bit
		 * (boot default) or 24-bit per channel. Per-sample stride is computed
		 * at runtime from Parser::m_emgChannelCount, not a fixed constant. */

		/* IMU payload: [ax,ay,az,gx,gy,gz] each int16 LE. */
		constexpr unsigned int IMU_AXES = 6;
		constexpr unsigned int IMU_SAMPLE_SIZE = 12; /* 6 × int16 */

		/* PPG payload: interleaved channels, each int24 LE. */
		constexpr unsigned int PPG_CHANNELS_2 = 2;
		constexpr unsigned int PPG_CHANNELS_4 = 4;
		constexpr unsigned int PPG_SAMPLE_SIZE_2CH = 6;  /* 2 × int24 */
		constexpr unsigned int PPG_SAMPLE_SIZE_4CH = 12; /* 4 × int24 */

		constexpr unsigned int SAMPLE_SIZE_16_BIT = 2;
		constexpr unsigned int SAMPLE_SIZE_24_BIT = 3;

		/* Boot-default full-scale (BMI323); overridden via SetImu*Ranges. */
		constexpr unsigned int IMU_ACC_RANGE_G_DEFAULT = 4;
		constexpr unsigned int IMU_GYR_RANGE_DPS_DEFAULT = 500;
		constexpr float IMU_RAW_PEAK = 32768.0f;

		/* EMG normalization divisor from resolution (matches EMG_RES_MAX GET). */
		constexpr float EMG_RES_MAX_16 = 32767.0f;
		constexpr float EMG_RES_MAX_24 = 4194304.0f; /* 0x400000 */

		/* PPG: AFE4950 count → µV (Pro_SDK scale_in_place). */
		constexpr float PPG_UV_PER_COUNT = (1.2f / 2097152.0f) * 1.0e6f; /* 1.2 / 2^21 */

		/*
		 * Decoder applies physical-unit scaling using host-pushed STATUS config:
		 *   EMG  → raw / emg_res_max  (32767 @ 16-bit, 0x400000 @ 24-bit)
		 *   Acc  → raw / 32768 * FS_g
		 *   Gyro → raw / 32768 * FS_dps
		 *   PPG  → raw * (1.2/2^21)*1e6   (µV)
		 */
	}
}
