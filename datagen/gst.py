"""GST reference data: state codes, GSTIN generation, and an item catalogue.

Rates in the catalogue are indicative, good enough to make synthetic invoices
look plausible. They are not a legal reference.
"""

from datetime import date

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# GST 2.0: the 12% and 28% slabs were folded into 5% / 18% (and 40% for
# demerit goods) from this date. Catalogue entries carry a rate for each era.
RATE_REFORM_DATE = date(2025, 9, 22)

# (GST state code, state name, some cities)
STATES = [
    ("29", "Karnataka", ["Bengaluru", "Hubballi", "Dharwad", "Mysuru", "Mangaluru", "Belagavi"]),
    ("27", "Maharashtra", ["Mumbai", "Pune", "Nagpur", "Nashik", "Kolhapur"]),
    ("33", "Tamil Nadu", ["Chennai", "Coimbatore", "Madurai", "Salem"]),
    ("36", "Telangana", ["Hyderabad", "Warangal", "Nizamabad"]),
    ("24", "Gujarat", ["Ahmedabad", "Surat", "Vadodara", "Rajkot"]),
    ("07", "Delhi", ["New Delhi", "Dwarka", "Rohini"]),
    ("09", "Uttar Pradesh", ["Lucknow", "Kanpur", "Noida", "Varanasi"]),
    ("19", "West Bengal", ["Kolkata", "Howrah", "Siliguri"]),
    ("32", "Kerala", ["Kochi", "Thiruvananthapuram", "Kozhikode"]),
    ("08", "Rajasthan", ["Jaipur", "Jodhpur", "Udaipur"]),
    ("06", "Haryana", ["Gurugram", "Faridabad", "Panipat"]),
    ("23", "Madhya Pradesh", ["Indore", "Bhopal", "Gwalior"]),
    ("37", "Andhra Pradesh", ["Vijayawada", "Visakhapatnam", "Guntur"]),
    ("03", "Punjab", ["Ludhiana", "Amritsar", "Jalandhar"]),
    ("30", "Goa", ["Panaji", "Margao"]),
    ("21", "Odisha", ["Bhubaneswar", "Cuttack"]),
    ("10", "Bihar", ["Patna", "Gaya"]),
    ("18", "Assam", ["Guwahati", "Dibrugarh"]),
]


def gstin_check_digit(first14: str) -> str:
    """Check character for the first 14 characters of a GSTIN (mod-36 Luhn variant)."""
    total = 0
    for i, ch in enumerate(first14):
        product = GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def is_valid_gstin(gstin: str) -> bool:
    return (
        len(gstin) == 15
        and all(c in GSTIN_CHARS for c in gstin)
        and gstin[13] == "Z"
        and gstin_check_digit(gstin[:14]) == gstin[14]
    )


def make_gstin(rng, state_code: str, holder_type: str = "") -> str:
    """Random, checksum-valid GSTIN. The 4th PAN letter encodes the holder type."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    holder = holder_type or rng.choice("CCCPPPFFHT")
    pan = (
        "".join(rng.choice(letters) for _ in range(3))
        + holder
        + rng.choice(letters)
        + "".join(rng.choice("0123456789") for _ in range(4))
        + rng.choice(letters)
    )
    body = state_code + pan + rng.choice("1111123") + "Z"
    return body + gstin_check_digit(body)


# Catalogue: category -> list of (description, HSN/SAC, rate before reform,
# rate after reform, min unit price, max unit price, unit, max quantity)
CATALOGUE = {
    "restaurant": [
        ("Masala Dosa", "996331", 5, 5, 60, 140, "Nos", 4),
        ("Idli Vada", "996331", 5, 5, 40, 90, "Nos", 4),
        ("Paneer Butter Masala", "996331", 5, 5, 180, 320, "Nos", 2),
        ("Butter Naan", "996331", 5, 5, 35, 70, "Nos", 6),
        ("Veg Biryani", "996331", 5, 5, 160, 280, "Nos", 3),
        ("Chicken Biryani", "996331", 5, 5, 220, 380, "Nos", 3),
        ("Gobi Manchurian", "996331", 5, 5, 120, 210, "Nos", 2),
        ("Dal Tadka", "996331", 5, 5, 130, 220, "Nos", 2),
        ("Jeera Rice", "996331", 5, 5, 110, 180, "Nos", 2),
        ("Filter Coffee", "996331", 5, 5, 20, 60, "Nos", 6),
        ("Masala Chai", "996331", 5, 5, 15, 45, "Nos", 6),
        ("Fresh Lime Soda", "996331", 5, 5, 50, 110, "Nos", 4),
        ("Gulab Jamun", "996331", 5, 5, 60, 120, "Nos", 4),
        ("North Indian Thali", "996331", 5, 5, 180, 350, "Nos", 4),
        ("Curd Rice", "996331", 5, 5, 70, 130, "Nos", 3),
        ("Tandoori Roti", "996331", 5, 5, 20, 45, "Nos", 8),
        ("Mineral Water 1L", "996331", 5, 5, 20, 40, "Nos", 4),
    ],
    "medical": [
        ("Paracetamol 500mg Tab 10s", "30049099", 12, 5, 18, 45, "Strip", 10),
        ("Amoxicillin 500mg Cap 10s", "30042019", 12, 5, 70, 140, "Strip", 6),
        ("Cetirizine 10mg Tab 10s", "30049031", 12, 5, 15, 40, "Strip", 10),
        ("Pantoprazole 40mg Tab 15s", "30049039", 12, 5, 90, 170, "Strip", 6),
        ("Metformin 500mg Tab 20s", "30049099", 12, 5, 30, 80, "Strip", 8),
        ("Cough Syrup 100ml", "30049099", 12, 5, 80, 150, "Btl", 4),
        ("ORS Powder Sachet 21g", "30049099", 12, 5, 18, 28, "Nos", 12),
        ("Vitamin C Chewable 500mg", "30045020", 12, 5, 25, 60, "Strip", 6),
        ("Digital Thermometer", "90251910", 12, 5, 150, 350, "Nos", 3),
        ("Surgical Gloves Pair", "40151100", 12, 5, 20, 55, "Pair", 20),
        ("Crepe Bandage 10cm", "30059040", 12, 5, 60, 130, "Nos", 6),
        ("Antiseptic Liquid 500ml", "38089400", 18, 18, 160, 260, "Btl", 4),
        ("Hand Sanitizer 200ml", "38089400", 18, 18, 70, 140, "Btl", 6),
        ("Glucose Test Strips 50s", "38220090", 12, 5, 600, 1100, "Box", 3),
    ],
    "clothing": [
        ("Mens Cotton Shirt", "62052000", 5, 5, 450, 990, "Pcs", 5),
        ("Mens Formal Trouser", "62034200", 12, 5, 1100, 2400, "Pcs", 4),
        ("Ladies Kurti", "62114200", 5, 5, 350, 950, "Pcs", 6),
        ("Silk Saree", "50072010", 12, 18, 2800, 9500, "Pcs", 3),
        ("Cotton Saree", "52085900", 5, 5, 500, 990, "Pcs", 5),
        ("Kids T-Shirt", "61091000", 5, 5, 180, 450, "Pcs", 8),
        ("Denim Jeans", "62034200", 12, 5, 1200, 2400, "Pcs", 4),
        ("Cotton Dupatta", "62149040", 5, 5, 150, 450, "Pcs", 6),
        ("Woollen Sweater", "61101120", 12, 5, 1100, 2300, "Pcs", 3),
        ("Bedsheet Double with Pillow Covers", "63041910", 5, 5, 600, 990, "Set", 4),
        ("Cotton Towel", "63026090", 5, 5, 120, 380, "Pcs", 10),
        ("Blazer", "62033300", 12, 18, 2800, 6500, "Pcs", 2),
    ],
    "electronics": [
        ("LED TV 43 inch Smart", "85287217", 28, 18, 21000, 34000, "Nos", 2),
        ("LED TV 32 inch HD Ready", "85287215", 18, 18, 9500, 14500, "Nos", 2),
        ("Split Air Conditioner 1.5 Ton", "84151010", 28, 18, 29000, 46000, "Nos", 2),
        ("Smartphone 6GB/128GB", "85171300", 18, 18, 9000, 26000, "Nos", 3),
        ("Laptop 15.6 inch 8GB/512GB", "84713010", 18, 18, 32000, 68000, "Nos", 3),
        ("Bluetooth Speaker", "85182100", 18, 18, 900, 3800, "Nos", 4),
        ("USB-C Charger 20W", "85044030", 18, 18, 350, 950, "Nos", 6),
        ("Wireless Mouse", "84716060", 18, 18, 350, 1100, "Nos", 6),
        ("Ceiling Fan 1200mm", "84145120", 18, 18, 1400, 3200, "Nos", 6),
        ("LED Bulb 9W", "85395000", 12, 5, 70, 140, "Nos", 20),
        ("Mixer Grinder 750W", "85094010", 18, 18, 2400, 5200, "Nos", 2),
        ("Refrigerator 190L", "84182100", 18, 18, 13500, 19000, "Nos", 1),
        ("HDMI Cable 1.5m", "85444299", 18, 18, 180, 480, "Nos", 6),
        ("Inkjet Printer", "84433100", 18, 18, 3800, 12500, "Nos", 2),
        ("UPS 600VA", "85044010", 18, 18, 2200, 3900, "Nos", 3),
    ],
    "grocery": [
        ("Basmati Rice 5kg Pack", "10063020", 5, 5, 420, 780, "Pkt", 4),
        ("Sunflower Oil 1L", "15121910", 5, 5, 125, 185, "Pkt", 6),
        ("Toor Dal 1kg Pack", "07136000", 5, 5, 130, 210, "Pkt", 5),
        ("Sugar 1kg", "17019990", 5, 5, 42, 58, "Kg", 10),
        ("Tea Powder 500g", "09024020", 5, 5, 180, 320, "Pkt", 4),
        ("Wheat Atta 10kg", "11010000", 5, 5, 380, 520, "Bag", 3),
        ("Ghee 500ml", "04059020", 12, 5, 290, 420, "Jar", 4),
        ("Biscuits Family Pack", "19053100", 18, 5, 40, 120, "Pkt", 10),
        ("Detergent Powder 1kg", "34022010", 18, 18, 95, 220, "Pkt", 6),
        ("Bath Soap 4x100g", "34011190", 18, 5, 110, 190, "Pkt", 6),
        ("Toothpaste 150g", "33061020", 18, 5, 85, 145, "Nos", 6),
        ("Instant Noodles 4 Pack", "19023010", 12, 5, 48, 70, "Pkt", 10),
        ("Fruit Jam 500g", "20079910", 12, 5, 130, 190, "Jar", 4),
        ("Shampoo 340ml", "33051090", 18, 5, 190, 340, "Btl", 4),
        ("Fresh Vegetables Assorted", "07099990", 0, 0, 30, 90, "Kg", 8),
        ("Milk 500ml", "04012000", 0, 0, 25, 34, "Pkt", 10),
    ],
    "hardware": [
        ("Portland Cement 50kg Bag", "25232930", 28, 18, 360, 440, "Bag", 120),
        ("TMT Steel Bar 12mm", "72142090", 18, 18, 58, 72, "Kg", 800),
        ("PVC Pipe 4 inch 6m", "39172390", 18, 18, 620, 980, "Nos", 40),
        ("Emulsion Paint 20L", "32091090", 28, 18, 2900, 5200, "Bkt", 10),
        ("Ceramic Floor Tile 2x2", "69072100", 18, 18, 38, 85, "Sqft", 900),
        ("Electrical Wire 1.5 sqmm 90m", "85444999", 18, 18, 1250, 1900, "Coil", 15),
        ("Plywood 18mm 8x4", "44123190", 18, 18, 2100, 3600, "Sheet", 25),
        ("Wall Putty 40kg", "32141000", 28, 18, 780, 1150, "Bag", 30),
        ("Modular Switch 6A", "85365090", 18, 18, 38, 95, "Nos", 100),
        ("Door Hinge SS 4 inch", "83021010", 18, 18, 65, 180, "Nos", 60),
        ("Binding Wire", "72171010", 18, 18, 62, 80, "Kg", 100),
        ("Sanitary Wash Basin", "69101000", 18, 18, 1400, 4200, "Nos", 6),
    ],
    "stationery": [
        ("A4 Copier Paper 500 Sheets", "48025690", 12, 18, 240, 340, "Ream", 40),
        ("Long Notebook 200 Pages", "48202000", 12, 0, 45, 90, "Nos", 100),
        ("Ball Pen Blue Pack of 10", "96081019", 18, 18, 45, 110, "Pkt", 30),
        ("Box File", "48203000", 18, 18, 75, 140, "Nos", 40),
        ("Stapler No.10", "84729010", 18, 18, 60, 160, "Nos", 12),
        ("Whiteboard Marker Set of 4", "96082000", 18, 18, 90, 180, "Set", 20),
        ("Pencil Box of 10", "96091000", 12, 0, 40, 80, "Box", 40),
        ("Printer Toner Cartridge", "84439959", 18, 18, 1400, 4200, "Nos", 6),
        ("Sticky Notes 3x3", "48209090", 18, 18, 30, 75, "Pad", 40),
        ("Geometry Box", "90172010", 12, 5, 80, 190, "Nos", 30),
    ],
    "auto_parts": [
        ("Engine Oil 5W-30 3.5L", "27101972", 18, 18, 1500, 2900, "Can", 6),
        ("Brake Pad Set Front", "87083000", 28, 18, 850, 2400, "Set", 6),
        ("Car Battery 35Ah", "85071000", 28, 18, 3600, 5400, "Nos", 3),
        ("Tubeless Tyre 185/65 R15", "40111010", 28, 18, 4100, 6300, "Nos", 4),
        ("Air Filter", "84213100", 18, 18, 280, 720, "Nos", 8),
        ("Clutch Plate Assembly", "87089300", 28, 18, 2400, 5600, "Nos", 3),
        ("Wiper Blade Pair", "85129000", 18, 18, 320, 850, "Pair", 6),
        ("Spark Plug", "85111000", 28, 18, 110, 320, "Nos", 12),
        ("Headlamp Assembly", "85122010", 18, 18, 1700, 4800, "Nos", 4),
        ("Coolant 1L", "38200000", 18, 18, 240, 420, "Btl", 8),
    ],
    "jewellery": [
        ("Gold Chain 22KT", "71131910", 3, 3, 42000, 135000, "Nos", 1),
        ("Gold Ring 22KT", "71131910", 3, 3, 16000, 48000, "Nos", 2),
        ("Gold Earrings 22KT Pair", "71131910", 3, 3, 22000, 64000, "Pair", 1),
        ("Silver Anklet Pair", "71131110", 3, 3, 3200, 9500, "Pair", 2),
        ("Silver Pooja Plate", "71141110", 3, 3, 5200, 18000, "Nos", 1),
        ("Gold Bangles 22KT Pair", "71131910", 3, 3, 68000, 190000, "Pair", 1),
        ("Diamond Nose Pin 18KT", "71131940", 3, 3, 7500, 22000, "Nos", 1),
    ],
    "services": [
        ("Software Development Services", "998314", 18, 18, 25000, 240000, "Job", 1),
        ("Annual Maintenance Contract", "998713", 18, 18, 8000, 65000, "Year", 1),
        ("Website Design and Hosting", "998315", 18, 18, 12000, 75000, "Job", 1),
        ("Accounting and Bookkeeping Charges", "998222", 18, 18, 3500, 28000, "Month", 3),
        ("GST Return Filing Fees", "998231", 18, 18, 1000, 5000, "Month", 3),
        ("Digital Marketing Retainer", "998361", 18, 18, 15000, 80000, "Month", 2),
        ("Manpower Supply Charges", "998519", 18, 18, 18000, 160000, "Month", 1),
        ("Security Guard Services", "998525", 18, 18, 22000, 95000, "Month", 1),
        ("Goods Transport Charges", "996511", 5, 5, 2500, 38000, "Trip", 4),
        ("Architectural Consultancy", "998321", 18, 18, 20000, 180000, "Job", 1),
        ("Housekeeping Services", "998533", 18, 18, 9000, 60000, "Month", 1),
        ("Legal Consultation Fees", "998212", 18, 18, 5000, 50000, "Job", 1),
        ("Equipment Rental Charges", "997319", 18, 18, 4000, 45000, "Month", 2),
        ("Installation and Commissioning", "998732", 18, 18, 3000, 40000, "Job", 1),
    ],
}

# Business-name suffixes per category.
VENDOR_SUFFIXES = {
    "restaurant": ["Restaurant", "Veg", "Family Restaurant", "Darshini", "Cafe", "Food Court",
                   "Tiffin Centre", "Hotel", "Dhaba", "Kitchen", "Bhavan", "Grand"],
    "medical": ["Medicals", "Medical Stores", "Pharma", "Pharmacy", "Medical & General Stores",
                "Drug House", "Healthcare", "Surgicals"],
    "clothing": ["Textiles", "Silks", "Fashions", "Garments", "Sarees", "Collections",
                 "Cloth Stores", "Readymades", "Dresses"],
    "electronics": ["Electronics", "Digital World", "Appliances", "Infotech", "Computers",
                    "Electricals", "Home Appliances", "Mobiles", "Sales & Service"],
    "grocery": ["Provision Stores", "Super Market", "Kirana Stores", "General Stores", "Traders",
                "Departmental Stores", "Mart", "Bazaar"],
    "hardware": ["Hardware", "Steels", "Building Materials", "Cement Agencies", "Paints & Hardware",
                 "Traders", "Tiles & Sanitary", "Enterprises"],
    "stationery": ["Stationery", "Book Depot", "Paper Mart", "Stationers", "Office Supplies",
                   "Book House", "Enterprises"],
    "auto_parts": ["Auto Parts", "Motors", "Automobiles", "Auto Spares", "Tyres", "Auto Agencies",
                   "Car Care"],
    "jewellery": ["Jewellers", "Gold Palace", "Jewellery Mart", "Jewels", "Bangle Stores",
                  "Gold & Diamonds"],
    "services": ["Technologies", "Consultants", "Solutions", "Associates", "Services", "Infotech",
                 "Logistics", "Facility Services", "Systems", "& Co", "Consultancy"],
}

NAME_ROOTS = [
    "Sri Lakshmi", "Shree Ganesh", "Sai", "Balaji", "Venkateshwara", "Annapurna", "Mahalaxmi",
    "Durga", "Shakti", "Sagar", "Kaveri", "Tunga", "Malnad", "Deccan", "Sahyadri", "Nandi",
    "Vijaya", "Jai Hind", "Bharat", "Navkar", "Ambika", "Krishna", "Raghavendra", "Basaveshwar",
    "Siddhi Vinayak", "Mahaveer", "Shanti", "Surya", "Chandra", "Ganga", "Himalaya", "Royal",
    "National", "Popular", "Modern", "New Janata", "City", "Metro", "Supreme", "Classic", "Star",
    "Golden", "Prakash", "Suresh", "Patil", "Kulkarni", "Hegde", "Shetty", "Reddy", "Agarwal",
    "Gupta", "Mehta", "Jain", "Desai", "Joshi", "Iyer", "Nair", "Menon", "Chopra", "Kapoor",
    "Banerjee", "Mukherjee", "Sharma", "Verma", "Singh", "Rao", "Naidu", "Pillai", "Bhat",
    "Kamat", "Pai", "Gowda", "Deshpande", "Shah", "Patel", "Trivedi", "Bose", "Das", "Khanna",
]

COMPANY_FORMS = ["", "", "", "", " Pvt Ltd", " Private Limited", " LLP", " & Sons", " & Co"]

FIRST_NAMES = [
    "Ramesh", "Suresh", "Mahesh", "Anil", "Sunil", "Vijay", "Rajesh", "Prakash", "Ganesh",
    "Manjunath", "Arun", "Kiran", "Naveen", "Praveen", "Santosh", "Deepak", "Amit", "Rahul",
    "Rohit", "Vinay", "Lakshmi", "Sunita", "Anita", "Kavita", "Priya", "Divya", "Pooja",
    "Sneha", "Meena", "Rekha", "Shilpa", "Asha", "Geeta", "Savita", "Nandini", "Aishwarya",
    "Mohammed", "Imran", "Joseph", "Thomas", "Gurpreet", "Harpreet", "Farhan", "Sandeep",
]

LAST_NAMES = [
    "Patil", "Kulkarni", "Hegde", "Shetty", "Reddy", "Agarwal", "Gupta", "Mehta", "Jain",
    "Desai", "Joshi", "Iyer", "Nair", "Sharma", "Verma", "Singh", "Rao", "Naidu", "Pillai",
    "Bhat", "Kamat", "Gowda", "Deshpande", "Shah", "Patel", "Das", "Khan", "Fernandes",
    "D'Souza", "Kaur", "Yadav", "Mishra", "Pandey", "Chavan", "Pawar", "Angadi", "Hiremath",
]

STREETS = [
    "M G Road", "Station Road", "Gandhi Bazaar", "Main Road", "Market Road", "College Road",
    "Nehru Nagar", "Industrial Area Phase II", "APMC Yard", "Old Bus Stand Road", "Court Circle",
    "Lamington Road", "Temple Street", "Ring Road", "Subhash Road", "Tilak Chowk", "P B Road",
    "Kalidasa Road", "Residency Road", "Sector 14", "Vidyanagar", "Rajajinagar 2nd Block",
    "Civil Lines", "Bank Colony", "Shivaji Nagar",
]

BANKS = [
    "State Bank of India", "Canara Bank", "Bank of Baroda", "Union Bank of India",
    "Karnataka Bank", "Indian Bank", "Punjab National Bank", "Bank of Maharashtra",
]
