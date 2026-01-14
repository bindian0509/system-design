package com.example.productsapi.service;

import com.example.productsapi.model.Product;
import com.example.productsapi.repository.ProductRepository;
import com.example.productsapi.web.dto.ProductRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class ProductService {

    private final ProductRepository repository;

    public ProductService(ProductRepository repository) {
        this.repository = repository;
    }

    public List<Product> findAll() {
        return repository.findAll();
    }

    public Product findById(UUID id) {
        return repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Product not found"));
    }

    public Product create(ProductRequest request) {
        Product product = new Product(
                UUID.randomUUID(),
                request.getName(),
                request.getDescription(),
                request.getPrice(),
                request.getStock(),
                Instant.now()
        );
        return repository.save(product);
    }

    public Product update(UUID id, ProductRequest request) {
        Product existing = findById(id);
        existing.setName(request.getName());
        existing.setDescription(request.getDescription());
        existing.setPrice(request.getPrice());
        existing.setStock(request.getStock());
        return repository.save(existing);
    }

    public void delete(UUID id) {
        Product existing = findById(id);
        repository.delete(existing);
    }
}
