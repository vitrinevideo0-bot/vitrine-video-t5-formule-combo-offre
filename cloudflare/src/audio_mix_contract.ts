// Generated from config/T5_AUDIO_MIX_V1_0_0.json; do not edit.
export const AUDIO_MIX_CONTRACT = {
  "$schema": "../schemas/T5_audio_mix.schema.json",
  "schema_version": "1.0.0",
  "id": "restauration_T5_four_track_rotation_voice_B_v1_0_0",
  "template_id": "RESTAURATION-T5",
  "status": "owner_approved_four_track_rotation_and_voice_ready_for_complete_render",
  "approved_on": "2026-11-18",
  "approval": "approvals/APPROBATION_MUSIQUE_ET_VOIX_T5_2026-11-18.json",
  "duration_s": 30.0,
  "sample_rate_hz": 48000,
  "scene_boundaries_s": [
    0.0,
    6.0,
    14.0,
    21.0,
    30.0
  ],
  "visual_stage": {
    "contract": "config/T5_RUNTIME_CONTRACT_V3_0_0.json",
    "text_motion": "config/T5_TEXT_MOTION_V4_0_0.json",
    "baseline_commit": "7650d07fcf0dea60ebc38fd45945db688696b4f6",
    "baseline_release": "https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/releases/tag/t5-full-frame-v3-candidate-7",
    "policy": "render silent visual, pass existing 21/21 QC, then mux complete audio while copying the H.264 bitstream"
  },
  "music": {
    "pack": "config/T5_MUSIC_PACK_V1_0_0.json",
    "selection_mode": "strict_success_cycle",
    "variant_count": 4,
    "state_update_policy": "after_completed_audio_qc_pass_only",
    "full_sources_bundled": false,
    "adapted_30s_instrumentals_bundled": true,
    "instrumentals_contain_voice": false,
    "program_target_lufs": -17.0,
    "program_true_peak_dbtp_max": -2.0
  },
  "voice": {
    "provider": "Arena.ai Agent Mode",
    "voice_id": "voice-11",
    "language": "fr",
    "identity": "masculine advertising",
    "selected_option": "B_masculine",
    "owner_selected_by_comparison": true,
    "manifest": "audio/voice/t5-voice-v1/manifest.json",
    "normalization_target_lufs": -20.0,
    "normalization_true_peak_dbtp_max": -3.0,
    "clips": [
      {
        "scene": 1,
        "scene_start_s": 0.0,
        "scene_end_s": 6.0,
        "start_s": 0.45,
        "text": "À Burger Atelier Kandi, découvre notre formule Double Burger.",
        "source": "audio/voice/t5-voice-v1/source/scene1.mp3",
        "source_sha256": "9fae7f38c1096538c9e31809be63efc4f74ba95d2f6d7ac3a1f6e8c27923d034",
        "source_duration_s": 5.32898
      },
      {
        "scene": 2,
        "scene_start_s": 6.0,
        "scene_end_s": 14.0,
        "start_s": 6.35,
        "text": "Un double burger généreux, une portion de frites croustillantes et un verre de cola bien frais.",
        "source": "audio/voice/t5-voice-v1/source/scene2.mp3",
        "source_sha256": "8f3fad37a9efa5f83838fdf5927eb070631c6004e740478582002f3d8268ba57",
        "source_duration_s": 7.497143
      },
      {
        "scene": 3,
        "scene_start_s": 14.0,
        "scene_end_s": 21.0,
        "start_s": 18.15,
        "text": "Le tout pour seulement cinq mille francs CFA.",
        "source": "audio/voice/t5-voice-v1/source/scene3.mp3",
        "source_sha256": "92e6bda7a2f55df44f7462c8e2e59561f5ad4bde3542c7c5b5df4c24e9e2a215",
        "source_duration_s": 2.76898
      },
      {
        "scene": 4,
        "scene_start_s": 21.0,
        "scene_end_s": 30.0,
        "start_s": 21.2,
        "text": "Une formule gourmande à savourer. Écris-nous sur WhatsApp et commande maintenant, près du marché central à Kandi.",
        "source": "audio/voice/t5-voice-v1/source/scene4.mp3",
        "source_sha256": "da6d9609bf17c6ffcf8f450317aed3ea144624bca46ec33ab5ce88c7eb13c244",
        "source_duration_s": 7.627755
      }
    ]
  },
  "mix_contract": {
    "music_open_gain_db": -3.0,
    "music_under_voice_gain_db": -10.0,
    "duck_depth_db": -7.0,
    "duck_attack_ms": 120,
    "duck_release_ms": 450,
    "duck_attack_curve": "linear_db",
    "duck_release_curve": "linear_db",
    "voice_gain_db": 0.0,
    "sfx": "none",
    "master_target_lufs": -16.0,
    "master_true_peak_dbtp_max": -2.0,
    "delivery_audio": "AAC stereo 48 kHz 192 kb/s"
  },
  "output": {
    "video_filename": "VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4",
    "master_audio_filename": "T5_MASTER_AUDIO_MUSIC_ROTATION_VOIX_B_30S.wav",
    "report_filename": "T5_COMPLETE_AUDIO_RENDER_REPORT.json"
  },
  "quality_gates": {
    "music_source_sha256_required": true,
    "exact_voice_clip_count": 4,
    "duration_tolerance_s": 0.025,
    "integrated_lufs_min": -16.6,
    "integrated_lufs_max": -15.4,
    "wav_true_peak_dbtp_max": -1.9,
    "aac_true_peak_dbtp_max": -1.0,
    "minimum_active_speech_to_music_db": 4.0,
    "clipped_sample_count_max": 0,
    "exact_frames": 900,
    "visual_bitstream_copy_required": true,
    "audio_codec": "aac",
    "audio_channels": 2,
    "audio_sample_rate_hz": 48000
  }
} as const;
export const AUDIO_MIX_CONTRACT_SHA256 = "c648217196738c35d5833b9a0eefa0f99fb6eba71808deb06aa6e87453c802ea" as const;
export const T5_VOICE_MANIFEST_SHA256 = "a69b3fc92897e9270817c07d5d639a63a661fe5c691820779cdd96f299a88914" as const;
