
# 🧰 Item Correction Management for ERPNext

**Author**: Ahmad Zubair Amini  
**ERPNext Compatibility**: v14 – v15  
**License**: [MIT](license.txt)  
**Repository**: [Item-Correction-Management](https://github.com/aogc-afg/Item-Correction-Management.git)

---

## 📖 Overview

This ERPNext module enables seamless conversion of **Asset Items** into **Stock Items**, including:

- Automated item flag conversion.
- Cleanup of asset records (depreciation, movement, etc.).
- Re-generation of stock ledger and bin records.
- GL entry corrections for Purchase Receipts and Purchase Invoices.

Designed for finance, stock, and asset managers who need to rectify asset misclassification efficiently.

---

## 🚀 Features

✅ Convert Fixed Asset item to Stock Item  
✅ Clean deletion of related `Asset`, `Depreciation`, and `Movement` records  
✅ Regenerates `Stock Ledger Entry` and `Bin` if missing  
✅ Creates/Updates GL entries for Purchase Receipts and Invoices  
✅ Tracks processed items to avoid duplication

---

## 🏗️ Doctypes

### 🔹 `AssettoStockItemConversion`
Main doctype. On submission, it triggers all related functions.

### 🔹 `Asset to Stock Processed`
Tracking log that stores each processed item to ensure no duplication.

---

## ⚙️ Core Functions

| Function | Purpose |
|----------|---------|
| `update_asset_to_stock_item(item_name)` | Converts item, deletes asset records, inserts stock ledger & bin entries |
| `update_receipt_gl_convert_asset_to_stock(item, category, account)` | Adjusts GL entries for Purchase Receipts |
| `update_invoice_gl_convert_asset_to_stock(item, category, account)` | Adjusts GL entries for Purchase Invoices |
| `recalculate_stock_valuation(item_code)` | Recomputes valuation rate and stock value per warehouse |

---

## 🔧 Setup & Installation

```bash
# Step 1: Clone the repository
cd ~/frappe-bench/apps/
git clone https://github.com/aogc-afg/Item-Correction-Management.git item_correction_management

# Step 2: Install the app on your site
cd ~/frappe-bench/
bench --site your-site-name install-app item_correction_management

# Step 3: Apply changes
bench migrate
````

---

## 🧑‍💻 Developer Notes

* ⚠️ GL Accounts such as `"Stock In Hand - AOGC"` are hardcoded. Consider replacing with dynamic configuration or system settings.
* ✅ Safe updates are temporarily disabled via `SET SQL_SAFE_UPDATES = 0`.
* 🔄 The process avoids re-processing by logging completed items in `Asset to Stock Processed`.
* 🔍 Serial number and batch tracking are not handled yet.
* 🏢 Multi-company support is partially included through company-based filters.

---

## 🧪 To-Do / Enhancements

* [ ] Dynamic account configuration via `Custom Settings`
* [ ] Add unit testing and test cases
* [ ] Improve user interface and error messages
* [ ] Add permission control based on roles
* [ ] Integrate with Asset Disposal logic
* [ ] Extend support for serial/batch tracked items

---

## 🤝 Contributing

We welcome all contributors! Please fork the repository and submit a pull request with your proposed changes.
For major features or improvements, open an issue first to discuss your ideas.

---

## 📬 Support

For bug reports, feature requests, or consultations, reach out to:
📧 **[zubairamini.cs@gmail.com](mailto:zubairamini.cs@gmail.com)**
🌐 [LinkedIn](https://www.linkedin.com/in/ahmad-zubair-amini-b45075182) (optional)

---

## 📄 License

This project is licensed under the terms of the [MIT license](license.txt).

---

```

---

### ✅ Next Steps:
- Save this content as your `README.md` inside the app's root folder.
- Optionally, add badges for GitHub stars, forks, license, etc., if you want a more public-facing polish.
- If you'd like a **Pashto or Dari version**, I can translate it as well.
```
