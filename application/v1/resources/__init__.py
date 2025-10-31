from application import api

from application.v1.resources.health import ns_health
# from application.v1.resources.auth import ns_auth

# from application.v1.resources.supply_points import supply_points_ns
# from application.v1.resources.customers import ns_customers
from application.v1.resources.media_tools import ns_media
from application.v1.resources.inpaint_image import ns_text_inpaint
from application.v1.resources.inpaint_video import ns_video_inpaint
from application.v1.resources.jobs import ns_jobs
from application.v1.resources.transcribe import ns_transcribe
from application.v1.resources.overlay_text import ns_overlay
from application.v1.resources.captions import ns_captions
from application.v1.resources.shuffle_video import ns_shuffle
from application.v1.resources.concat_video import ns_concat
from application.v1.resources.edit_resize import ns_resize
from application.v1.resources.audio_normalize import ns_anorm
from application.v1.resources.audio_mix import ns_amix
from application.v1.resources.detect_scenes import ns_scenes
from application.v1.resources.captions_translate import ns_ctran
from application.v1.resources.audio_denoise import ns_denoise
from application.v1.resources.video_rotate import ns_rotate
from application.v1.resources.video_speed import ns_speed
from application.v1.resources.video_stabilize_cv import ns_stab_cv
from application.v1.resources.video_watermark import ns_wm
from application.v1.resources.video_trim import ns_trim
from application.v1.resources.video_crop import ns_crop
from application.v1.resources.video_color import ns_color


api.add_namespace(ns_health)
# api.add_namespace(ns_auth)

# api.add_namespace(supply_points_ns)
# api.add_namespace(ns_customers)
api.add_namespace(ns_media)
api.add_namespace(ns_text_inpaint)
api.add_namespace(ns_video_inpaint)
api.add_namespace(ns_jobs)
api.add_namespace(ns_transcribe)
api.add_namespace(ns_overlay)
api.add_namespace(ns_captions)
api.add_namespace(ns_shuffle)
api.add_namespace(ns_concat)
api.add_namespace(ns_resize)
api.add_namespace(ns_anorm)
api.add_namespace(ns_amix)
api.add_namespace(ns_scenes)
api.add_namespace(ns_ctran)
api.add_namespace(ns_denoise)
api.add_namespace(ns_rotate)
api.add_namespace(ns_speed)
api.add_namespace(ns_stab_cv)
api.add_namespace(ns_wm)
api.add_namespace(ns_trim)
api.add_namespace(ns_crop)
api.add_namespace(ns_color)

