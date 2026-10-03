"""Roboti laborikalibratsiooni laadimine ja valideerimine."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CALIBRATION_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "robot_calibration.json"
)


class CalibrationError(ValueError):
    """Kalibratsioonifaili struktuur või väärtus ei ole lubatud."""


class IncompleteCalibrationError(CalibrationError):
    """Kalibratsioon vajab enne kasutamist laborimõõtmisi."""


@dataclass(frozen=True)
class WorkspaceCalibration:
    origin_x: float | None
    origin_y: float | None
    width: float | None
    height: float | None


@dataclass(frozen=True)
class PoseCalibration:
    r: float | None
    pen_up_z: float | None
    pen_down_z: float | None


@dataclass(frozen=True)
class MotionCalibration:
    speed_percent: float | None


@dataclass(frozen=True)
class PaperCalibration:
    """Kaks õpetatud punkti lehe alumisel serval (vt src/paper.py)."""

    corner_x: float | None = None
    corner_y: float | None = None
    edge_x: float | None = None
    edge_y: float | None = None
    size: str = "A4"
    orientation: str = "portrait"
    margin_mm: float = 15.0
    # Mõõdetud lehe mõõdud; kui mõlemad on antud, kehtivad need size asemel
    # (03.10.26: õpetatud alumiste nurkade vahe oli 264 mm, mitte 297).
    width_mm: float | None = None
    height_mm: float | None = None

    @property
    def is_complete(self) -> bool:
        return None not in (self.corner_x, self.corner_y, self.edge_x, self.edge_y)


@dataclass(frozen=True)
class RobotCalibration:
    version: int
    workspace: WorkspaceCalibration
    pose: PoseCalibration
    motion: MotionCalibration
    paper: PaperCalibration = PaperCalibration()

    @property
    def is_complete(self) -> bool:
        """Tagasta tõene ainult siis, kui kõik laboriväärtused on olemas."""
        values = (
            self.workspace.origin_x,
            self.workspace.origin_y,
            self.workspace.width,
            self.workspace.height,
            self.pose.r,
            self.pose.pen_up_z,
            self.pose.pen_down_z,
            self.motion.speed_percent,
        )
        return all(value is not None for value in values)

    def require_complete(self) -> None:
        """Peata ohutult tegevus, mis vajab täielikku kalibratsiooni."""
        if not self.is_complete:
            raise IncompleteCalibrationError(
                "roboti kalibratsioon on puudulik; mõõda väärtused laboris"
            )

    def require_text_ready(self) -> None:
        """Teksti joonistamiseks on vaja pliiatsi poosi, kiirust ja lehte."""
        values = (
            self.pose.r,
            self.pose.pen_up_z,
            self.pose.pen_down_z,
            self.motion.speed_percent,
        )
        if any(value is None for value in values) or not self.paper.is_complete:
            raise IncompleteCalibrationError(
                "teksti kalibratsioon on puudulik; mõõda pose, motion ja paper laboris"
            )


def _object(document: object, key: str) -> dict[str, object]:
    if not isinstance(document, dict):
        raise CalibrationError("kalibratsiooni juur peab olema JSON objekt")
    value = document.get(key)
    if not isinstance(value, dict):
        raise CalibrationError(f"{key} peab olema JSON objekt")
    return value


def _nullable_number(section: dict[str, object], key: str, location: str) -> float | None:
    if key not in section:
        raise CalibrationError(f"{location}.{key} puudub")
    value = section[key]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError(f"{location}.{key} peab olema arv või null")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise CalibrationError(f"{location}.{key} peab olema lõplik arv")
    return numeric


def validate_robot_calibration(document: object) -> RobotCalibration:
    """Valideeri versiooni 1 kalibratsioon; null-väärtused on lubatud."""
    if not isinstance(document, dict):
        raise CalibrationError("kalibratsiooni juur peab olema JSON objekt")
    version = document.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise CalibrationError("kalibratsiooni version peab olema täisarv 1")

    workspace_data = _object(document, "workspace")
    pose_data = _object(document, "pose")
    motion_data = _object(document, "motion")

    workspace = WorkspaceCalibration(
        origin_x=_nullable_number(workspace_data, "origin_x", "workspace"),
        origin_y=_nullable_number(workspace_data, "origin_y", "workspace"),
        width=_nullable_number(workspace_data, "width", "workspace"),
        height=_nullable_number(workspace_data, "height", "workspace"),
    )
    if workspace.width is not None and workspace.width <= 0:
        raise CalibrationError("workspace.width peab olema positiivne")
    if workspace.height is not None and workspace.height <= 0:
        raise CalibrationError("workspace.height peab olema positiivne")

    pose = PoseCalibration(
        r=_nullable_number(pose_data, "r", "pose"),
        pen_up_z=_nullable_number(pose_data, "pen_up_z", "pose"),
        pen_down_z=_nullable_number(pose_data, "pen_down_z", "pose"),
    )
    motion = MotionCalibration(
        speed_percent=_nullable_number(motion_data, "speed_percent", "motion")
    )
    if motion.speed_percent is not None and not 0 < motion.speed_percent <= 100:
        raise CalibrationError("motion.speed_percent peab olema vahemikus 0 < väärtus <= 100")

    paper = _paper(document)
    return RobotCalibration(version, workspace, pose, motion, paper)


def _optional_positive(data: dict[str, object], key: str) -> float | None:
    if key not in data:
        return None
    value = _nullable_number(data, key, "paper")
    if value is not None and value <= 0:
        raise CalibrationError(f"paper.{key} peab olema positiivne")
    return value


def _paper(document: dict[str, object]) -> PaperCalibration:
    """Valikuline sektsioon: vanad failid ilma paper-osata jäävad kehtima."""
    if "paper" not in document:
        return PaperCalibration()
    data = _object(document, "paper")
    size = data.get("size", "A4")
    orientation = data.get("orientation", "portrait")
    if size not in ("A5", "A4", "A3", "Letter"):
        raise CalibrationError("paper.size peab olema A5, A4, A3 või Letter")
    if orientation not in ("portrait", "landscape"):
        raise CalibrationError("paper.orientation peab olema portrait või landscape")
    margin = _nullable_number({"margin_mm": data.get("margin_mm", 15.0)}, "margin_mm", "paper")
    if margin is None or margin < 0:
        raise CalibrationError("paper.margin_mm peab olema mittenegatiivne arv")
    paper = PaperCalibration(
        corner_x=_nullable_number(data, "corner_x", "paper"),
        corner_y=_nullable_number(data, "corner_y", "paper"),
        edge_x=_nullable_number(data, "edge_x", "paper"),
        edge_y=_nullable_number(data, "edge_y", "paper"),
        size=str(size),
        orientation=str(orientation),
        margin_mm=margin,
        width_mm=_optional_positive(data, "width_mm"),
        height_mm=_optional_positive(data, "height_mm"),
    )
    if (paper.width_mm is None) != (paper.height_mm is None):
        raise CalibrationError("paper.width_mm ja paper.height_mm antakse koos")
    if paper.is_complete:
        baseline = math.hypot(paper.edge_x - paper.corner_x, paper.edge_y - paper.corner_y)  # type: ignore[operator]
        if baseline < 50.0:
            raise CalibrationError(
                "paper.edge peab olema nurgast vähemalt 50 mm kaugusel lehe alumisel serval"
            )
    return paper


def load_robot_calibration(
    path: str | Path = DEFAULT_CALIBRATION_PATH,
) -> RobotCalibration:
    """Laadi JSON-fail ja tagasta valideeritud kalibratsioon."""
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CalibrationError(f"kalibratsioonifaili ei saa lugeda: {source}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationError(f"vigane JSON kalibratsioonifailis: {source}") from exc
    return validate_robot_calibration(document)
