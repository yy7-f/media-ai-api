from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.inpaint_image_service import InpaintImageService

ns_text_inpaint = Namespace(
    "TextInpaint",
    path="/inpaint/",
    description="Automatic text removal / inpainting using LaMa model."
)

parser = ns_text_inpaint.parser()
parser.add_argument("image", location="files", type=FileStorage, required=True, help="Image (png/jpg/jpeg/webp)")
parser.add_argument("ocr_langs", location="form", required=False, help="OCR languages (default en)")
parser.add_argument("device", location="form", required=False, help="cpu|cuda (default cpu)")


@ns_text_inpaint.route("/image")
class InpaintImageResource(Resource):
    @ns_text_inpaint.expect(parser)
    @ns_text_inpaint.doc(description="Upload an image; removes text automatically using OCR + LaMa inpainting.")
    def post(self):
        args = parser.parse_args()
        img_file = args.get("image")
        if not img_file:
            return {"message": "No image uploaded"}, 400

        ocr_langs = (request.values.get("ocr_langs") or "en")
        device = (request.values.get("device") or "cpu")

        try:
            upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("INPAINT_OUTPUT", "inpaint_output")

            image_path = InpaintImageService.save_upload(img_file, upload_dir=upload_dir)
            svc = InpaintImageService(image_path=image_path,
                                      work_root=upload_dir,
                                      output_root=output_root)

            result = svc.process_lama(ocr_langs=ocr_langs, device=device)
            svc.cleanup()

            return jsonify({
                "status": "ok",
                "result_path": result["output_path"],
                "filename": result["filename"],
                "diagnostics": result["diagnostics"]
            })
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
