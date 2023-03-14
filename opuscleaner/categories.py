import os
import json
from fastapi import FastAPI
from pydantic import BaseModel, parse_obj_as, validator
from typing import Any, List, Dict, TextIO, cast

from opuscleaner.config import CATEGORIES_PATH, DATA_PATH, DEFAULT_CATEGORIES


class Category(BaseModel):
	name: str

	@validator('name')
	def name_must_not_be_empty(cls, value:str) -> str:
		assert len(value.strip()) > 0, 'must not be empty'
		return value.strip()


class CategoryMapping(BaseModel):
	categories: List[Category]
	mapping: Dict[str,List[str]]

	@validator('categories')
	def categories_must_be_unique(cls, value:List[Category]) -> List[Category]:
		assert len(set(category.name.strip() for category in value)) == len(value), 'categories must have unique names'
		return value

	@validator('mapping')
	def mapping_must_only_contain_categories(cls, value:Dict[str,List[str]], values: Dict[str,Any], **kwargs) -> Dict[str,List[str]]:
		assert len(set(value.keys()) - set(category.name.strip() for category in values.get('categories', ''))) == 0, 'mapping must only contain keys that are defined in `categories`'
		return value


def read_categories(fh:TextIO) -> CategoryMapping:
	return parse_obj_as(CategoryMapping, json.load(fh))

def write_categories(mapping:CategoryMapping, fh:TextIO) -> None:
	json.dump(mapping.dict(), fh, indent=2)


app = FastAPI()

@app.get('/')
def get_mapping() -> CategoryMapping:
	if os.path.exists(CATEGORIES_PATH):
		with open(CATEGORIES_PATH, 'r') as fh:
			return read_categories(fh)
	else:
		return CategoryMapping(categories=DEFAULT_CATEGORIES, mapping=dict())

@app.put('/')
def update_categories(body:CategoryMapping) -> None:
	with open(CATEGORIES_PATH, 'w') as fh:
		write_categories(body, fh)
