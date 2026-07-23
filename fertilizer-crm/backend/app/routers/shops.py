from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import ShopMaster
from app.schemas.crm import ShopMasterCreate, ShopMasterUpdate, ShopMasterOut

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.get("", response_model=list[ShopMasterOut])
def list_shops(region: str = None, active_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(ShopMaster).order_by(ShopMaster.region, ShopMaster.shop_name)
    if region:
        q = q.filter(ShopMaster.region == region)
    if active_only:
        q = q.filter(ShopMaster.is_active == True)
    return q.all()


@router.post("", response_model=ShopMasterOut, status_code=201)
def create_shop(payload: ShopMasterCreate, db: Session = Depends(get_db)):
    s = ShopMaster(**payload.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return s


@router.get("/{shop_id}", response_model=ShopMasterOut)
def get_shop(shop_id: int, db: Session = Depends(get_db)):
    s = db.get(ShopMaster, shop_id)
    if not s:
        raise HTTPException(404, "ไม่พบร้านค้า")
    return s


@router.put("/{shop_id}", response_model=ShopMasterOut)
def update_shop(shop_id: int, payload: ShopMasterUpdate, db: Session = Depends(get_db)):
    s = db.get(ShopMaster, shop_id)
    if not s:
        raise HTTPException(404, "ไม่พบร้านค้า")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return s


@router.delete("/{shop_id}", status_code=204)
def delete_shop(shop_id: int, db: Session = Depends(get_db)):
    s = db.get(ShopMaster, shop_id)
    if not s:
        raise HTTPException(404, "ไม่พบร้านค้า")
    db.delete(s); db.commit()


@router.post("/seed", status_code=201)
def seed_shops(db: Session = Depends(get_db)):
    """Seed ข้อมูลจาก SHOP_MASTER constant เข้า DB (ใช้ครั้งเดียว)"""
    existing = db.query(ShopMaster).count()
    if existing > 0:
        return {"status": "skipped", "message": f"มีข้อมูลแล้ว {existing} ร้าน"}
    SHOP_MASTER = [
        {"name":"ไพบูรณ์การเกษตร","region":"อีสานตอนบน"},{"name":"บัวทองนที","region":"อีสานตอนบน"},
        {"name":"เดชพาณิชย์","region":"อีสานตอนบน"},{"name":"ชาตรีการเกษตร","region":"อีสานตอนบน"},
        {"name":"บุญมีรุ่งเรืองอินเตอร์เทรด","region":"อีสานตอนบน"},{"name":"กล้า น้ำ ข้าว ทรัพย์เกษตร","region":"อีสานตอนบน"},
        {"name":"ดวงพรการเกษตร/ส่งเสริม","region":"อีสานตอนบน"},{"name":"เอ็น.ดี.เอฟ","region":"อีสานตอนบน"},
        {"name":"แสงรุ่งเรือง","region":"อีสานตอนบน"},{"name":"รัตนชัยการเกษตร","region":"อีสานตอนบน"},
        {"name":"ฮั่วหลีชัยภูมิ","region":"อีสานตอนบน"},{"name":"ไทยการค้าดงเย็น","region":"อีสานตอนบน"},
        {"name":"เขียวดีการเกษตร","region":"อีสานตอนบน"},{"name":"วุฒิผ่องพืชผล","region":"อีสานตอนบน"},
        {"name":"ไคฮวดการเกษตร","region":"อีสานตอนบน"},{"name":"ต้นข้าวเกษตรพันธุ์","region":"อีสานตอนบน"},
        {"name":"อ.รุ่งเรืองการเกษตร","region":"อีสานตอนบน"},{"name":"ดินดีทรัพย์เกษตร","region":"อีสานตอนบน"},
        {"name":"นพชัยการเกษตร","region":"อีสานตอนบน"},{"name":"ยิ่งการเกษตร","region":"อีสานตอนบน"},
        {"name":"มหาเฮง เคมีเกษตรภัณฑ์","region":"อีสานตอนบน"},{"name":"ก.เกษตร (2012) จำกัด","region":"อีสานตอนบน"},
        {"name":"รุ่งระวีการเกษตร","region":"อีสานตอนบน"},{"name":"หนองบัวใหญ่","region":"อีสานตอนบน"},
        {"name":"ดอกคูณการเกษตร","region":"อีสานตอนบน"},{"name":"เมล็ดพันธุ์การเกษตร","region":"อีสานตอนบน"},
        {"name":"รุ่งเรืองชัยเกษตรนากลาง","region":"อีสานตอนบน"},{"name":"พ.พืชผล","region":"อีสานตอนบน"},
        {"name":"แก่นการเกษตร","region":"อีสานตอนบน"},{"name":"เกษเคมีภัณฑ์","region":"อีสานตอนบน"},
        {"name":"คลีนิคเกษตร","region":"อีสานตอนบน"},
        {"name":"ศักดิ์เสนาการเกษตร/รวม","region":"อีสานตอนล่าง"},{"name":"รุ่งเกษตร","region":"อีสานตอนล่าง"},
        {"name":"จึงเจริญการเกษตร","region":"อีสานตอนล่าง"},{"name":"ทรัพย์ทวี","region":"อีสานตอนล่าง"},
        {"name":"แสงอรุณพาณิชย์","region":"อีสานตอนล่าง"},{"name":"ปราสาทเกษตรภัณฑ์","region":"อีสานตอนล่าง"},
        {"name":"กิตติพงษ์ทรัพย์เกษตร","region":"อีสานตอนล่าง"},{"name":"กิจรุ่งเรืองการเกษตร","region":"อีสานตอนล่าง"},
        {"name":"ส.นิยม","region":"อีสานตอนล่าง"},{"name":"ทองพูนการเกษตร","region":"อีสานตอนล่าง"},
        {"name":"เพื่อนเกษตรสังขะ","region":"อีสานตอนล่าง"},{"name":"ทรัพย์มงคลการเกษตร 1","region":"อีสานตอนล่าง"},
        {"name":"น.เกษตร ปักธงชัย","region":"อีสานตอนล่าง"},{"name":"ศรีเสถียรการเกษตร/บุญมาก","region":"อีสานตอนล่าง"},
        {"name":"ตังนันต์เกษตร","region":"อีสานตอนล่าง"},{"name":"เกษตรธรรมชาติ/เจริญพัฒนา","region":"อีสานตอนล่าง"},
        {"name":"ชญานุตย์พาณิชย์","region":"อีสานตอนล่าง"},{"name":"ศรีโพธิไทรการเกษตร","region":"อีสานตอนล่าง"},
        {"name":"รุ่งเรืองการค้า","region":"อีสานตอนล่าง"},{"name":"ศักดิ์รุ่งเรือง","region":"อีสานตอนล่าง"},
        {"name":"มเหสักข์รุ่งเรืองการเกษตร","region":"อีสานตอนล่าง"},{"name":"แทนคุณการเกษตร","region":"อีสานตอนล่าง"},
        {"name":"รุ่งทรัพย์เกษตร 2","region":"อีสานตอนล่าง"},{"name":"ทรัพย์มงคล 2","region":"อีสานตอนล่าง"},
        {"name":"ทองมาเฟอร์นิเจอร์","region":"อีสานตอนล่าง"},{"name":"แคนดงการเกษตร","region":"อีสานตอนล่าง"},
        {"name":"โนนไทยอาหารสัตว์","region":"อีสานตอนล่าง"},{"name":"สหกรณ์เลิงนกทา","region":"อีสานตอนล่าง"},
        {"name":"วิทยาการเกษตร","region":"อีสานตอนล่าง"},{"name":"กิมไถ่การเกษตร","region":"อีสานตอนล่าง"},
        {"name":"บัวเกษตร","region":"อีสานตอนล่าง"},{"name":"เปรมชัย","region":"อีสานตอนล่าง"},
        {"name":"พฤกษาภัณฑ์","region":"ตะวันออก"},{"name":"ชัยพฤกษ์ตรีรัตน์","region":"ตะวันออก"},
        {"name":"เกษตรวัฒนา","region":"ตะวันออก"},{"name":"ชัยพฤกษ์เขาไร่ยา","region":"ตะวันออก"},
        {"name":"ชัยพฤกษ์ ไดร์ฟทรู","region":"ตะวันออก"},{"name":"ชัยพฤกษ์ทับไทร","region":"ตะวันออก"},
        {"name":"โลกเกษตร","region":"ตะวันออก"},{"name":"เพื่อนเกษตรแสนตุ้ง","region":"ตะวันออก"},
        {"name":"หนุ่มแซร์ออร์","region":"ตะวันออก"},{"name":"นายาวการเกษตร","region":"ตะวันออก"},
        {"name":"บุญเจริญทรัพย์เกษตร","region":"ตะวันออก"},{"name":"ก้องการเกษตร","region":"ตะวันออก"},
        {"name":"บุญชัยการเกษตร","region":"ตะวันออก"},{"name":"กมลวรรณการเกษตร","region":"ตะวันออก"},
        {"name":"สองเกษตร","region":"ตะวันออก"},{"name":"ซอย8รุ่งเรืองค้า","region":"ตะวันออก"},
        {"name":"ปังธงเฮง (อบแพทย์)","region":"ตะวันออก"},{"name":"ทิพย์การเกษตร","region":"ตะวันออก"},
        {"name":"นิลกาฬการเกษตร","region":"ตะวันออก"},{"name":"รุ่งทรัพย์เกษตร","region":"ตะวันออก"},
        {"name":"ทวีเกษตร2","region":"กลาง"},{"name":"สำรวยการเกษตร","region":"กลาง"},
        {"name":"เพรชศิริอนันต์เคมีเกษตร","region":"กลาง"},{"name":"คมคิดการเกษตร","region":"กลาง"},
        {"name":"ทวีเกษตร3","region":"กลาง"},{"name":"หนองกร่างการเกษตร","region":"กลาง"},
        {"name":"ภูธารการเกษตร","region":"กลาง"},{"name":"เพลาพิราศ","region":"กลาง"},
        {"name":"ตาตือ","region":"กลาง"},{"name":"โก๋การเกษตร","region":"กลาง"},
        {"name":"เพื่อนเกษตร-64","region":"กลาง"},{"name":"อำนาจเกษตรสิงห์","region":"กลาง"},
        {"name":"นาทองเคมีเกษตร","region":"กลาง"},{"name":"เกษตรแทนคุณ","region":"กลาง"},
        {"name":"ดีเด่นอะโกเทรด","region":"กลาง"},{"name":"มาลีพัน์ข้าว","region":"กลาง"},
        {"name":"จตุพรการเกษตร","region":"เหนือ"},{"name":"บ้านร่องบงมิตรเกษตร","region":"เหนือ"},
        {"name":"เสน่ห์การเกษตร","region":"เหนือ"},{"name":"สวนสมหมายการเกษตร","region":"เหนือ"},
        {"name":"เงินทองมาก้าวหน้า","region":"เหนือ"},{"name":"ธัญธวัชพืชผล","region":"เหนือ"},
        {"name":"ภาวินการเกษตร","region":"เหนือ"},{"name":"ป.ทรัพย์เกษตร","region":"เหนือ"},
        {"name":"บุญดามิตรเกษตร","region":"เหนือ"},{"name":"หจก. เอสเคเพื่อนเกษตร","region":"เหนือ"},
        {"name":"พัชรพรการเกษตร","region":"เหนือ"},{"name":"ชาญชัยการเกษตร","region":"เหนือ"},
        {"name":"คลองเจริญ","region":"เหนือ"},{"name":"ศิริทรัพย์","region":"เหนือ"},
        {"name":"ธนพร","region":"เหนือ"},{"name":"ส.กิจเริญ","region":"เหนือ"},
        {"name":"แผ่นดินเกษตร","region":"เหนือ"},{"name":"ห้วงสลิด","region":"เหนือ"},
        {"name":"โรงสีโชคสงวนทรัพย์","region":"เหนือ"},{"name":"เกษตร99","region":"เหนือ"},
        {"name":"พิมเพื่อนเกษตร","region":"เหนือ"},{"name":"เกษตรเจริญทรัพย์","region":"เหนือ"},
        {"name":"ภัสสรเคมี","region":"เหนือ"},{"name":"แม่จามิตรเกษตร","region":"เหนือ"},
        {"name":"อเนก เคมีเกษตร","region":"ใต้"},{"name":"ส.เจริญสหกิจ","region":"ใต้"},
        {"name":"เกียร์การเกษตร","region":"ใต้"},{"name":"ดร.สมพร","region":"ใต้"},
        {"name":"วัชระพานิช","region":"ใต้"},{"name":"จำเริญการเกษตร","region":"ใต้"},
        {"name":"ถาวรการเกษตร","region":"ใต้"},{"name":"พีพีการเกษตร","region":"ใต้"},
        {"name":"บ้านเกษตร","region":"ใต้"},{"name":"พงษ์เกษตรภัณฑ์","region":"ใต้"},
        {"name":"ทุ่งใหญ่การเกษตร 1995 จำกัด","region":"ใต้"},{"name":"อารีการเกษตร","region":"ใต้"},
        {"name":"ป่าถล่ม","region":"ใต้"},{"name":"บรรดิษฐการเกษตร","region":"ใต้"},
        {"name":"พรหมบุตรการเกษตร","region":"ใต้"},{"name":"จิตเกษตร","region":"ใต้"},
        {"name":"สมบูรณ์การเกษตร","region":"ใต้"},{"name":"ณัฐกิตติ์เกษตรภัณฑ์","region":"ใต้"},
        {"name":"ไก่เกษตร","region":"ใต้"},{"name":"ทุ่งระโนด","region":"ใต้"},
        {"name":"โกดังเพื่อนเกษตร","region":"ใต้"},{"name":"บ้านหมอการเกษตร","region":"ใต้"},
        {"name":"วิจิตรการเกษตร","region":"ใต้"},{"name":"เกษตรยิ้ม","region":"ใต้"},
        {"name":"หัวถนน","region":"ใต้"},{"name":"เอี๊ยวเจริญ","region":"ใต้"},
        {"name":"อุดมทรัพย์การเกษตร","region":"ใต้"},{"name":"ปรีดากการเกษตร","region":"ใต้"},
        {"name":"ทุ่งหว้าสหภัณฑ์","region":"ใต้"},{"name":"ไชโย","region":"ใต้"},
    ]
    count = 0
    for s in SHOP_MASTER:
        db.add(ShopMaster(shop_name=s["name"], region=s["region"]))
        count += 1
    db.commit()
    return {"status": "ok", "seeded": count}
