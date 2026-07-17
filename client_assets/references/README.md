# Reference Image Library

Drop high-performing Instagram ad images here by industry.
When image generation runs, Fal.ai uses these as style anchors (image-to-image).
The AI inherits composition, lighting, and aesthetic — while generating content for the new client.

## How to add references

1. Find 2-5 real Instagram ads that performed well in the industry
2. Save them as `.jpg` files in the matching subfolder
3. The pipeline auto-detects industry and picks the first reference image found

## Folder structure

```
references/
├── home_services/     # Plumbing, HVAC, electrical, roofing, landscaping
├── food_beverage/     # Coffee shops, restaurants, cafes, bakeries
├── health_beauty/     # Salons, spas, nail, massage, barbers
├── health_fitness/    # Gyms, yoga, personal training, CrossFit
├── retail/            # Boutiques, clothing, jewelry, gifts
└── professional_services/  # Law, accounting, finance, real estate
```

## How it works

- With a reference image: Fal.ai runs `flux/dev` image-to-image at strength=0.75
  → Keeps ~75% of the reference's visual style, replaces content with the client's scene
- Without a reference: Falls back to pure text-to-image generation
  → Still uses the industry-specific image_prompt from the AI, just less style-consistent

## What makes a good reference

- Real photos, not stock art or AI-generated
- High contrast, clear subject, simple composition
- Successful ad performance is the best signal
- Avoid text-heavy images (the text gets inherited by the AI)
