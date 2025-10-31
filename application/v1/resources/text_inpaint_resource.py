from flask_restx import Resource, Namespace
from application.workers import api_key_required
from application.v1.services.text_inpaint_service import TextInpaintService

ns_text_inpaint = Namespace(
    "TextInpaint",
    path="/text-inpaint/",
    description="API endpoints for removing overlay text via OCR + inpainting."
)


@ns_text_inpaint.route("/remove/")
class TextInpaintRemoveResource(Resource):
    @ns_text_inpaint.doc(
        security="apikey",
        description=(
            "Upload a video file to remove detected overlay text using EasyOCR + LaMa (iopaint). "
            "Form fields: file (required), ocr_langs='en', fps=30, device in {'cpu','cuda'}."
        )
    )
    @api_key_required
    def post(self):
        response, code = TextInpaintService().process()
        return response, code
